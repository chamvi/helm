"""Run the fixture image (ci/app, the published @chamvi packages) the way the chart's CronJob does."""
import os
import subprocess
import unittest

import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE = os.environ.get("AGENT_APP_CI_IMAGE")


@unittest.skipUnless(IMAGE, "set AGENT_APP_CI_IMAGE (make fixture builds chamvi-ci/app:ci)")
class FixtureContract(unittest.TestCase):
    def test_cron_job_args_complete_a_run(self):
        values = yaml.safe_load((ROOT / "charts/agent-app/ci/cronjob-values.yaml").read_text())
        job = values["cronJobs"][0]
        args = ["node", "node_modules/@chamvi/cli/dist/cli.mjs", "run-job", job["agent"], job["subscription"]]
        result = subprocess.run(
            ["docker", "run", "--rm", "--read-only", "--tmpfs", "/tmp", "-u", "1000:1000",
             "-e", "CHAMVI_LOG_LEVEL=error", IMAGE, *args],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, rf"^{job['agent']}: completed \(run [0-9a-f-]+\)$")
