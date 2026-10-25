"""The audit must find missing nested keys without rejecting free-form maps."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "check-values-coverage.py"


class ValuesCoverage(unittest.TestCase):
    def test_declared_and_free_form_keys_pass_but_missing_nested_key_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            chart = Path(folder)
            (chart / "templates").mkdir()
            (chart / "values.yaml").write_text("image:\n  tag: test\nglobal: {}\n")
            template = chart / "templates/example.tpl"
            template.write_text("{{ .Values.image.tag }} {{ .Values.global.parent }}")
            result = subprocess.run(["python3", str(SCRIPT), str(chart)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            template.write_text("{{ .Values.image.repository }}")
            result = subprocess.run(["python3", str(SCRIPT), str(chart)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("image.repository", result.stdout)


if __name__ == "__main__":
    unittest.main()
