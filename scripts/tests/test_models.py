"""Model/provider validation must also hold when Helm schema checks are skipped."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

CHART = Path(__file__).resolve().parents[2] / "charts/agent-app"


class Models(unittest.TestCase):
    def render(self, values):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
            yaml.safe_dump({"image": {"repository": "example/app", "tag": "test"}, **values}, file)
            file.flush()
            return subprocess.run(
                ["helm", "template", "test", str(CHART), "--skip-schema-validation", "-f", file.name],
                capture_output=True, text=True,
            )

    def test_invalid_settings_fail_without_echoing_credentials(self):
        for values in [
            {"providers": {"Bad": {"type": "anthropic"}}},
            {"providers": {"team": "secret-sentinel"}},
            {"providers": {"team": {"type": "anthropic", "headers": "secret-sentinel"}}},
            {"providers": {"team": {"type": "anthropic", "headers": {"authorization": "secret-sentinel"}}}},
            {"providers": {"team": {"type": "anthropic", "apiKey": {"secretName": "valid", "key": ""}}}},
            {"providers": {"team": {"type": "anthropic", "headers": {"x-team": {"value": "plain", "valueFrom": {"secretKeyRef": {"name": "valid", "key": "key"}}}}}}},
            {"providers": {"team": {"type": "anthropic"}}, "env": {"CHAMVI_PROVIDER_TEAM_TYPE": "secret-sentinel"}},
            {"providers": {"team": {"type": "anthropic", "headers": {"x-team": {"value": "plain"}}}}, "env": {"CHAMVI_PROVIDER_TEAM_HEADER_X_TEAM": "secret-sentinel"}},
            {"providers": {"team": {"type": "unknown"}}},
            {"providers": {"team": {"type": "openai-compatible"}}},
            {"providers": {"team": {"type": "anthropic", "apiKey": "secret-sentinel"}}},
            {"providers": {"team": {"type": "anthropic", "baseURL": "https://secret-sentinel@example.com"}}},
            {"providers": {"team": {"type": "anthropic", "headers": {"authorization": {"value": "secret-sentinel"}}}}},
            {"model": "team/id", "env": {"CHAMVI_MODEL": "secret-sentinel"}},
        ]:
            with self.subTest(values=values):
                result = self.render(values)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("secret-sentinel", result.stderr)

    def test_provider_header_env_collisions_are_rejected(self):
        cases = [
            ({"type": "anthropic"}, "b-type"),
            ({"type": "anthropic", "baseURL": "https://models.example.test"}, "b-base-url"),
            ({"type": "anthropic", "apiKey": {"secretName": "models", "key": "api-key"}}, "b-api-key"),
            ({"type": "anthropic", "headers": {"c": {"value": "plain"}}}, "b-header-c"),
        ]
        for provider, header in cases:
            with self.subTest(header=header):
                result = self.render({"providers": {
                    "a": {"type": "anthropic", "headers": {header: {
                        "valueFrom": {"secretKeyRef": {"name": "models", "key": "secret-sentinel"}},
                    }}},
                    "a-header-b": provider,
                }})
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("duplicate environment variable names", result.stderr)
                self.assertNotIn("secret-sentinel", result.stderr)

    def test_unemitted_optional_provider_fields_do_not_collide_with_headers(self):
        for header, env_name in [
            ("b-base-url", "CHAMVI_PROVIDER_A_HEADER_B_BASE_URL"),
            ("b-api-key", "CHAMVI_PROVIDER_A_HEADER_B_API_KEY"),
        ]:
            with self.subTest(header=header):
                result = self.render({"providers": {
                    "a": {"type": "anthropic", "headers": {header: {
                        "valueFrom": {"secretKeyRef": {"name": "models", "key": "header"}},
                    }}},
                    "a-header-b": {"type": "anthropic"},
                }})
                self.assertEqual(result.returncode, 0, result.stderr)
                deployment = next(doc for doc in yaml.safe_load_all(result.stdout) if doc and doc["kind"] == "Deployment")
                env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
                self.assertEqual([entry for entry in env if entry["name"] == env_name],
                                 [{"name": env_name, "valueFrom": {
                                     "secretKeyRef": {"name": "models", "key": "header"},
                                 }}])

    def test_defaults_emit_no_model_settings(self):
        result = self.render({})
        self.assertEqual(result.returncode, 0, result.stderr)
        for doc in yaml.safe_load_all(result.stdout):
            if doc and doc.get("kind") == "Deployment":
                env = doc["spec"]["template"]["spec"]["containers"][0]["env"]
                self.assertFalse(any(item["name"] == "CHAMVI_MODEL" or item["name"].startswith("CHAMVI_PROVIDER_") for item in env))

    def test_cron_jobs_share_model_env_and_hook_does_not(self):
        result = self.render({
            "model": "team/id",
            "providers": {"team": {
                "type": "anthropic",
                "apiKey": {"secretName": "model-credentials", "key": "api-key"},
                "headers": {
                    "x-team": {"value": "platform"},
                    "authorization": {"valueFrom": {"secretKeyRef": {"name": "model-credentials", "key": "authorization"}}},
                },
            }},
            "cronJobs": [{"name": "daily", "schedule": "0 0 * * *", "agent": "example"}],
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        resources = list(yaml.safe_load_all(result.stdout))
        deployment = next(item for item in resources if item and item.get("kind") == "Deployment")
        cron = next(item for item in resources if item and item.get("kind") == "CronJob")
        for pod in [deployment["spec"]["template"]["spec"], cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]]:
            env = pod["containers"][0]["env"]
            self.assertIn({"name": "CHAMVI_MODEL", "value": "team/id"}, env)
            self.assertIn({"name": "CHAMVI_PROVIDER_TEAM_API_KEY", "valueFrom": {"secretKeyRef": {"name": "model-credentials", "key": "api-key"}}}, env)
            self.assertIn({"name": "CHAMVI_PROVIDER_TEAM_HEADER_X_TEAM", "value": "platform"}, env)
            self.assertIn({"name": "CHAMVI_PROVIDER_TEAM_HEADER_AUTHORIZATION", "valueFrom": {"secretKeyRef": {"name": "model-credentials", "key": "authorization"}}}, env)
            self.assertEqual(len(env), len({item["name"] for item in env}))
        for item in resources:
            if item and "helm.sh/hook" in item.get("metadata", {}).get("annotations", {}):
                self.assertNotIn("CHAMVI_MODEL", yaml.safe_dump(item))
