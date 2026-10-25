"""release-please and hevi wiring: one linked version for root and the chart, published to ghcr.io/chamvi/helm."""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class Release(unittest.TestCase):
    def test_versions_agree(self):
        chart = yaml.safe_load((ROOT / "charts/agent-app/Chart.yaml").read_text())
        manifest = json.loads((ROOT / ".release-please-manifest.json").read_text())
        self.assertEqual(manifest, {".": chart["version"], "charts/agent-app": chart["version"]})
        self.assertEqual((ROOT / "version.txt").read_text().strip(), chart["version"])

    def test_root_is_a_real_release_linked_to_the_chart(self):
        config = json.loads((ROOT / "release-please-config.json").read_text())
        self.assertFalse(config["include-v-in-tag"])
        self.assertTrue(config["bump-minor-pre-major"])
        self.assertTrue(config["bump-patch-for-minor-pre-major"])
        self.assertEqual(config["packages"]["."], {"component": "root", "release-type": "simple"})
        self.assertEqual(
            config["packages"]["charts/agent-app"],
            {"component": "agent-app", "release-type": "helm", "skip-github-release": True, "extra-files": ["README.md"]},
        )
        self.assertEqual(
            config["plugins"],
            [{"type": "linked-versions", "groupName": "global", "components": ["root", "agent-app"]}],
        )

    def test_release_please_keeps_every_readme_version_in_step(self):
        # release-please's helm strategy bumps Chart.yaml only; README.md (an extra-file) changes on annotated lines,
        # so every chart version in it must sit on such a line, or `make drift` fails after the release PR.
        version = yaml.safe_load((ROOT / "charts/agent-app/Chart.yaml").read_text())["version"]
        template = (ROOT / "charts/agent-app/README.md.gotmpl").read_text()
        self.assertNotIn("chart.badgesSection", template)
        self.assertNotIn("chart.versionBadge", template)
        inside = False
        found = 0
        for line in (ROOT / "charts/agent-app/README.md").read_text().splitlines():
            if "x-release-please-start-version" in line:
                inside = True
            elif "x-release-please-end" in line:
                inside = False
            elif version in line:
                found += 1
                self.assertTrue(inside or "x-release-please-version" in line, line)
                # The generic updater replaces the first semver of a line and eats a following "-word" as a prerelease.
                self.assertEqual(line.count(version), 1, line)
                self.assertFalse(line.split(version, 1)[1][:1] in ("-", "+"), line)
        self.assertGreater(found, 0)

    def test_maintainers_carry_an_email_for_artifacthub(self):
        # ArtifactHub's Helm tracker drops maintainers without an email.
        chart = yaml.safe_load((ROOT / "charts/agent-app/Chart.yaml").read_text())
        self.assertTrue(chart["maintainers"])
        for maintainer in chart["maintainers"]:
            self.assertRegex(maintainer.get("email", ""), r"^[^@\s]+@[^@\s]+\.[a-z]+$")

    def test_publish_is_ungated_and_pushes_to_the_chamvi_registry(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release.yaml").read_text())
        triggers = workflow[True]  # PyYAML reads the bare key `on` as True
        self.assertIn("workflow_dispatch", triggers)
        self.assertEqual(triggers["push"]["branches"], ["master"])
        publish = workflow["jobs"]["publish"]
        self.assertEqual(publish["if"], "${{ !cancelled() && needs.release-please.result != 'failure' }}")
        hevi = next(s for s in publish["steps"] if s.get("uses", "").startswith("tada5hi/hevi@"))
        self.assertEqual(hevi["uses"], "tada5hi/hevi@v2")
        self.assertEqual(hevi["with"]["push-host"], "ghcr.io/${{ github.repository_owner }}/helm")
        self.assertTrue(hevi["with"]["push-skip-existing"])
        helm = next(s for s in publish["steps"] if s.get("uses", "").startswith("azure/setup-helm@"))
        self.assertEqual(helm["with"]["version"], "v4.3.1")


if __name__ == "__main__":
    unittest.main()
