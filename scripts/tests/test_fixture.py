"""Execute the fixture with already-built workspace packages, not a registry install."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FixtureContract(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CHAMVI_APP_MODULE"), "requires built workspace app")
    def test_ping_job_completes_against_real_app(self):
        modules = Path(os.environ["CHAMVI_APP_MODULE"]).resolve().parents[3] / "node_modules"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "node_modules").symlink_to(modules, target_is_directory=True)
            shutil.copy(ROOT / "ci/app/dist/index.mjs", root / "index.mjs")
            result = subprocess.run(["node", "--input-type=module", "-e", """
                const { default: app } = await import(process.argv[1]);
                const result = await app.runJob({agent:'ping', subscription:'cron:0 0 1 1 *', env:{CHAMVI_LOG_LEVEL:'error'}});
                if (result.status !== 'completed' || result.exitCode !== 0) throw new Error(JSON.stringify(result));
                console.log(result.status);
            """, (root / "index.mjs").as_uri()], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "completed")
