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
            {"component": "agent-app", "release-type": "helm", "skip-github-release": True},
        )
        self.assertEqual(
            config["plugins"],
            [{"type": "linked-versions", "groupName": "global", "components": ["root", "agent-app"]}],
        )

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
