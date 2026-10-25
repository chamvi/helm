"""The docs follow the current chamvi contract, and the README's Flux example renders."""
import subprocess
import tempfile
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "charts/agent-app"
# Names the chamvi contract dropped (plan 026 channels, approvals without resume tokens).
STALE = ["RESUME_SECRET", "/webhooks/github", "@chamvi/scheduler", "@chamvi/notify-", "consoleNotifierModule", "triggers:"]
SKIP_DIRS = {".git", ".local", "node_modules", "__pycache__"}


def text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not SKIP_DIRS & set(path.relative_to(ROOT).parts) and path.parent != Path(__file__).parent:
            if path.suffix in {".md", ".gotmpl", ".txt", ".yaml", ".yml", ".tpl", ".mjs", ".json", ".sh", ".py"} or path.name == "Makefile":
                yield path


def flux_values():
    readme = (CHART / "README.md").read_text()
    for block in readme.split("```yaml")[1:]:
        for doc in yaml.safe_load_all(block.split("```")[0]):
            if doc and doc.get("kind") == "HelmRelease":
                return doc["spec"]["values"]
    raise AssertionError("README.md has no HelmRelease example")


def flux_examples(path):
    docs = [doc for block in path.read_text().split("```yaml")[1:] for doc in yaml.safe_load_all(block.split("```")[0]) if doc]
    source = next((d for d in docs if d.get("kind") == "OCIRepository"), None)
    release = next((d for d in docs if d.get("kind") == "HelmRelease"), None)
    return source, release


class Docs(unittest.TestCase):
    def test_flux_examples_keep_the_chart_source_next_to_the_release(self):
        # helm-controller with --no-cross-namespace-refs=true refuses a chartRef into another namespace.
        for path in [ROOT / "README.md", CHART / "README.md.gotmpl", CHART / "README.md"]:
            source, release = flux_examples(path)
            self.assertIsNotNone(source, f"{path.relative_to(ROOT)} has no OCIRepository example")
            namespace = release["metadata"]["namespace"]
            self.assertEqual(source["metadata"]["namespace"], namespace, path.relative_to(ROOT))
            self.assertEqual(release["spec"]["chartRef"]["namespace"], namespace, path.relative_to(ROOT))

    def test_no_stale_contract_names(self):
        for path in text_files():
            text = path.read_text(errors="ignore")
            for name in STALE:
                self.assertNotIn(name, text, f"{path.relative_to(ROOT)} mentions {name}")

    def test_readme_flux_example_renders_the_acceptance_shape(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
            yaml.safe_dump(flux_values(), file)
            file.flush()
            result = subprocess.run(
                ["helm", "template", "triage", str(CHART), "-n", "agents", "-f", file.name],
                capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        deployment = next(d for d in yaml.safe_load_all(result.stdout) if d and d["kind"] == "Deployment")
        pod = deployment["spec"]["template"]
        container = pod["spec"]["containers"][0]
        self.assertEqual(deployment["spec"]["strategy"], {"type": "Recreate"})
        self.assertEqual(container["args"], ["node", "node_modules/@chamvi/cli/dist/cli.mjs", "start"])
        self.assertNotIn("command", container)
        self.assertNotIn("imagePullSecrets", pod["spec"])
        self.assertEqual(pod["spec"]["securityContext"]["runAsUser"], 1000)
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(pod["metadata"]["labels"]["app.kubernetes.io/component"], "app")
        self.assertEqual(container["lifecycle"], {"preStop": {"sleep": {"seconds": 5}}})
        self.assertEqual(pod["spec"]["terminationGracePeriodSeconds"], 120)
        self.assertEqual(container["startupProbe"]["httpGet"]["path"], "/healthz")
        env = {e["name"]: e["value"] for e in container["env"]}
        self.assertEqual(env["CHAMVI_PUBLIC_URL"], "https://agents.example.com")


if __name__ == "__main__":
    unittest.main()
