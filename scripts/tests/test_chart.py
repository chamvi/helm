"""Render-boundary checks, including YAML types and duplicate SSA keys."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "charts/agent-app"
BASE = {"image": {"repository": "example.invalid/agent", "tag": "test"}}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    pairs = loader.construct_pairs(node)
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError(f"Duplicate YAML key: {key}")
        result[key] = value
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def render(values=None, release="demo", chart=CHART, extra=()):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
        yaml.safe_dump({**BASE, **(values or {})}, file)
        file.flush()
        return subprocess.run(
            ["helm", "template", release, str(chart), "--namespace", "agents", "-f", file.name, *extra],
            capture_output=True, text=True,
        )


def documents(result):
    if result.returncode:
        raise AssertionError(result.stderr)
    return [doc for doc in yaml.load_all(result.stdout, Loader=UniqueLoader) if doc]


class ChartContract(unittest.TestCase):
    def test_invalid_values_fail_without_echoing_credentials(self):
        # Mutation: removing a guard should admit at least one invalid manifest.
        cases = [
            ({"env": {"PASSWORD": {"value": "sensitive-sentinel"}}}, "env.PASSWORD"),
            ({"env": {"PASSWORD": ["sensitive-sentinel"]}}, "env.PASSWORD"),
            ({"env": {"PASSWORD": "sensitive-sentinel\x00"}}, "env.PASSWORD"),
            ({"env": {"CHAMVI_FORCE_EXIT_MS": "sensitive-sentinel"}}, "CHAMVI_FORCE_EXIT_MS"),
            ({"env": {"CHAMVI_FORCE_EXIT_MS": "2147483648"}}, "CHAMVI_FORCE_EXIT_MS"),
            ({"env": {"CHAMVI_FORCE_EXIT_MS": "999999999999999999999999"}}, "CHAMVI_FORCE_EXIT_MS"),
            ({"env": {"CHAMVI_FORCE_EXIT_MS": False}}, "CHAMVI_FORCE_EXIT_MS"),
            ({"env": {"CHAMVI_FORCE_EXIT_MS": "115000"}}, "terminationGracePeriodSeconds"),
            ({"env": {"CHAMVI_BASE_PATH": "/other"}}, "CHAMVI_BASE_PATH"),
            ({"secrets": ["sensitive-sentinel/invalid"]}, "secrets"),
            ({"secrets": ["shared", "shared"]}, "secrets"),
            ({"secrets": [{"token": "sensitive-sentinel"}]}, "secrets"),
            ({"secrets": "sensitive-sentinel"}, "secrets"),
            ({"ingress": {"enabled": True}}, "ingress.host"),
            ({"ingress": {"enabled": True, "host": "https://bad/path"}}, "ingress.host"),
            ({"fullnameOverride": "has_underscore"}, "fullnameOverride"),
            ({"fullnameOverride": "123"}, "fullnameOverride"),
            ({"nameOverride": "a" * 64}, "nameOverride"),
            ({"replicass": 2}, "replicass"),
            ({"replicas": 0}, "replicas"),
            ({"replicas": "2"}, "replicas"),
            ({"sandbox": {"enabled": "false"}}, "sandbox.enabled"),
            ({"ingress": {"enabled": "false", "host": "agents.example.com"}}, "ingress.enabled"),
            ({"serviceAccount": {"create": "false"}}, "serviceAccount.create"),
            ({"tests": {"enabled": "false"}}, "tests.enabled"),
            ({"imagePullSecrets": [{"name": "sensitive-sentinel/invalid"}]}, "imagePullSecrets"),
            ({"imagePullSecrets": [{"name": "shared"}, {"name": "shared"}]}, "imagePullSecrets"),
            ({"strategy": {"type": "Recreate", "rollingUpdate": {"maxSurge": 1}}}, "strategy"),
            ({"service": {"port": 65536}}, "service.port"),
            ({"preStopSleepSeconds": -1}, "preStopSleepSeconds"),
            ({"terminationGracePeriodSeconds": 0}, "terminationGracePeriodSeconds"),
            ({"command": []}, "command"),
            ({"command": ["node", 2]}, "command"),
            ({"podAnnotations": {"number": 42}}, "podAnnotations"),
            ({"podLabels": {"helm.sh/chart": "other"}}, "podLabels"),
            ({"podLabels": {"chamvi.dev/cron-job": "other"}}, "podLabels"),
            ({"probes": {"startup": {"httpGet": {"path": "/wrong"}}}}, "probes.startup"),
            ({"probes": {"liveness": {"exec": {"command": ["true"]}}}}, "probes.liveness"),
            ({"probes": {"startup": {"periodSeconds": 0}}}, "probes.startup"),
        ]
        # The schema answers first (a JSON pointer); the template guards must still hold
        # for a render that skips it (helm --skip-schema-validation).
        for values, field in cases:
            for extra in ((), ("--skip-schema-validation",)):
                with self.subTest(values=values, extra=extra):
                    result = render(values, extra=extra)
                    self.assertNotEqual(result.returncode, 0)
                    names = (field,) if extra else (field, "/" + field.replace(".", "/"))
                    self.assertTrue(any(n in result.stderr for n in names), result.stderr)
                    self.assertNotIn("sensitive-sentinel", result.stderr)

    def test_cron_validation_and_conditional_owned_env(self):
        job = {"name": "digest", "agent": "digest", "schedule": "0 7 * * *"}
        cases = [
            {"cronJobs": [job, job]},
            {"cronJobs": [{**job, "name": "a" * 21}]},
            {"cronJobs": [{**job, "agent": "Digest"}]},
            {"cronJobs": [{**job, "agent": "a" * 65}]},
            {"cronJobs": [{**job, "schedule": " "}]},
            {"cronJobs": [{**job, "subscription": 1}]},
            {"cronJobs": [{**job, "subscription": "--entry"}]},
            {"cronJobs": [{**job, "unknown": True}]},
            {"cronJobs": [job], "env": {"CHAMVI_SCHEDULER": "true"}},
            {"sandbox": {"enabled": True, "namespace": "sandboxes"}, "env": {"CHAMVI_SANDBOX_NAMESPACE": "other"}},
        ]
        for values in cases:
            with self.subTest(values=values):
                self.assertNotEqual(render(values).returncode, 0)
        documents(render({"env": {"CHAMVI_SCHEDULER": "false", "CHAMVI_SANDBOX_NAMESPACE": "external"}}))

    def test_scalar_names_and_env_are_strings_and_unique(self):
        docs = documents(render({
            "fullnameOverride": "true", "nameOverride": "123",
            "secrets": ["123"], "podLabels": {"on": "true"},
            "env": {"BOOL": False, "ZERO": 0, "NUMBER": 1.25, "TEXT": "on", "MULTILINE": "a\nb"},
        }))
        for doc in docs:
            self.assertIsInstance(doc["metadata"]["name"], str)
        pod = next(d for d in docs if d["kind"] == "Deployment")["spec"]["template"]
        self.assertEqual(pod["metadata"]["labels"]["on"], "true")
        container = pod["spec"]["containers"][0]
        env = container["env"]
        self.assertEqual(len(env), len({entry["name"] for entry in env}))
        self.assertEqual({entry["name"]: entry["value"] for entry in env}, {
            "PORT": "3000", "CHAMVI_BASE_PATH": "", "BOOL": "false", "ZERO": "0", "NUMBER": "1.25", "TEXT": "on", "MULTILINE": "a\nb",
        })
        self.assertEqual(container["envFrom"], [{"secretRef": {"name": "123"}}])

    def test_empty_public_url_is_unset_and_origin_is_emitted_once(self):
        docs = documents(render({
            "basePath": "/agents",
            "ingress": {"enabled": True, "host": "agents.example.com"},
            "env": {"CHAMVI_PUBLIC_URL": ""},
        }))
        env = next(d for d in docs if d["kind"] == "Deployment")["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual([entry for entry in env if entry["name"] == "CHAMVI_PUBLIC_URL"], [
            {"name": "CHAMVI_PUBLIC_URL", "value": "http://agents.example.com"},
        ])

    def test_names_and_job_arguments_survive_long_inputs(self):
        for length in [3, 20, 40, 53]:
            docs = documents(render({"cronJobs": [
                {"name": "digest", "agent": "a" * 64, "schedule": "0 7 * * *", "subscription": "cron:0 7 * * *"},
                {"name": "other", "agent": "digest", "schedule": "0 7 * * *"},
            ]}, release="a" * length))
            seen = set()
            for doc in docs:
                name = doc["metadata"]["name"]
                self.assertRegex(name, r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
                identity = (doc["kind"], name)
                self.assertNotIn(identity, seen)
                seen.add(identity)
                if doc["kind"] == "Pod":
                    self.assertTrue(name.endswith("-test"))
                if doc["kind"] == "CronJob":
                    self.assertLessEqual(len(name), 52)
                    self.assertTrue(name.endswith(("-digest", "-other")))
                    if name.endswith("-digest"):
                        args = doc["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["args"]
                        self.assertEqual(args[-2:], ["a" * 64, "cron:0 7 * * *"])

    def test_differing_length_cron_suffixes_have_unique_stable_names(self):
        values = {
            "fullnameOverride": "a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a-a",
            "cronJobs": [
                {"name": "x", "agent": "digest", "schedule": "0 7 * * *"},
                {"name": "a-x", "agent": "digest", "schedule": "0 8 * * *"},
                {"name": "abcdefghijklmnopqrst", "agent": "digest", "schedule": "0 9 * * *"},
            ],
        }
        jobs = [doc for doc in documents(render(values)) if doc["kind"] == "CronJob"]
        names = [job["metadata"]["name"] for job in jobs]
        self.assertEqual(len(set(names)), len(names))
        for job, name in zip(values["cronJobs"], names):
            self.assertLessEqual(len(name), 52)
            self.assertRegex(name, r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
            self.assertTrue(name.endswith("-" + job["name"]))
        repeated = [doc["metadata"]["name"] for doc in documents(render(values)) if doc["kind"] == "CronJob"]
        self.assertEqual(names, repeated)

    def test_duplicate_final_cron_identity_is_rejected(self):
        # Force a helper collision to exercise the final-identity guard independently.
        with tempfile.TemporaryDirectory() as folder:
            chart = Path(folder) / "agent-app"
            shutil.copytree(CHART, chart)
            helper = chart / "templates/_helpers.tpl"
            text = helper.read_text()
            start = text.index('{{- define "agent-app.componentName" -}}')
            end = text.index('{{- define "agent-app.chart" -}}', start)
            helper.write_text(text[:start] + '{{- define "agent-app.componentName" -}}collision{{- end -}}\n\n' + text[end:])
            result = render({"cronJobs": [
                {"name": "x", "agent": "digest", "schedule": "0 7 * * *"},
                {"name": "a-x", "agent": "digest", "schedule": "0 8 * * *"},
            ]}, chart=chart)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rendered CronJob name", result.stderr)

    def test_packaged_chart_preserves_readiness_hook(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(["helm", "package", str(CHART), "--destination", folder], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            version = yaml.safe_load((CHART / "Chart.yaml").read_text())["version"]
            docs = documents(render(chart=Path(folder) / f"agent-app-{version}.tgz"))
            hooks = [d for d in docs if d["kind"] == "Pod"]
            self.assertEqual(len(hooks), 1)
            self.assertEqual(hooks[0]["metadata"]["annotations"]["helm.sh/hook"], "test")

    @unittest.skipUnless(os.environ.get("AGENT_APP_CI_IMAGE"), "set AGENT_APP_CI_IMAGE (make fixture builds chamvi-ci/app:ci)")
    def test_rendered_origin_builds_approval_link_with_one_base_path(self):
        docs = documents(render({"basePath": "/agents", "ingress": {"enabled": True, "host": "agents.example.com", "tls": {"secretName": "tls"}}}))
        env = next(d for d in docs if d["kind"] == "Deployment")["spec"]["template"]["spec"]["containers"][0]["env"]
        script = """
            const { readConfig, approvalUrlOf } = await import('@chamvi/app');
            const env = JSON.parse(process.argv[1]);
            const config = readConfig(env, { mode: 'start', dev: false });
            console.log(approvalUrlOf(config)({runId:'run-1',approvalId:'0:call:0',agent:'digest'}));
        """
        result = subprocess.run(
            ["docker", "run", "--rm", "-u", "1000:1000", os.environ["AGENT_APP_CI_IMAGE"],
             "node", "--input-type=module", "-e", script, json.dumps({e["name"]: e["value"] for e in env})],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "https://agents.example.com/agents/ui/approvals?run=run-1&approval=0%3Acall%3A0")

if __name__ == "__main__":
    unittest.main()
