"""The ct install matrix: every ci values file installs against the pre-applied manifests."""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "charts/agent-app"
MANIFESTS = CHART / "ci/manifests"
# Variables the current chamvi app no longer reads; a CI Secret must not suggest them.
OBSOLETE = {"RESUME_SECRET"}


def manifest_secrets():
    secrets = {}
    for path in sorted(MANIFESTS.glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if doc and doc.get("kind") == "Secret":
                secrets[doc["metadata"]["name"]] = doc
    return secrets


class CiMatrix(unittest.TestCase):
    def test_every_install_file_names_a_pre_applied_secret(self):
        secrets = manifest_secrets()
        files = sorted((CHART / "ci").glob("*-values.yaml"))
        self.assertEqual(
            [f.name for f in files],
            ["cronjob-values.yaml", "default-values.yaml", "ingress-values.yaml", "sandbox-values.yaml"],
        )
        for path in files:
            values = yaml.safe_load(path.read_text())
            self.assertEqual(values["image"], {"repository": "chamvi-ci/app", "tag": "ci", "pullPolicy": "Never"}, path.name)
            for name in values.get("secrets", []):
                self.assertIn(name, secrets, f"{path.name}: Secret {name} is not in ci/manifests")

    def test_ci_secret_holds_static_tokens_and_no_obsolete_variables(self):
        secret = manifest_secrets()["agent-app-ci"]
        data = secret["stringData"]
        self.assertFalse(OBSOLETE & set(data), "obsolete variables in the CI Secret")
        tokens = json.loads(data["CHAMVI_TOKENS"])
        self.assertTrue(tokens and all(len(t["value"]) >= 16 and t["id"] and isinstance(t["permissions"], list) for t in tokens))
        self.assertNotIn("namespace", secret["metadata"], "ct install applies it into a fresh namespace")

    def test_cronjob_file_mirrors_the_fixture_cron_subscription(self):
        values = yaml.safe_load((CHART / "ci/cronjob-values.yaml").read_text())
        fixture = (ROOT / "ci/app/dist/index.mjs").read_text()
        for job in values["cronJobs"]:
            expression = job["subscription"].removeprefix("cron:")
            self.assertEqual(job["schedule"], expression)
            self.assertIn(f"cron.on('{expression}')", fixture)
            self.assertIn(f"name: '{job['agent']}'", fixture)

    def test_fixture_installs_the_published_packages(self):
        package = json.loads((ROOT / "ci/app/package.json").read_text())
        deps = package["dependencies"]
        for name in ("@chamvi/app", "@chamvi/cli"):
            self.assertTrue(deps[name].startswith("^0.2."), f"{name} must track the published 0.2 line")


if __name__ == "__main__":
    unittest.main()
