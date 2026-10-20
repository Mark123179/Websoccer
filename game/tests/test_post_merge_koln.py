"""Exercise shell ordering without migrations, database writes or regression runs."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase


class PostMergeKolnTests(SimpleTestCase):
    script = Path(__file__).resolve().parents[2] / "scripts/post-merge.sh"

    def run_hook(self, *, enabled=False, refuse_alignment=False, regression_exit=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "bin"
            tools.mkdir()
            python = tools / "python3"
            python.write_text(
                "#!/bin/sh\n"
                'echo "$*" >> "$TEST_CALLS"\n'
                'if [ "$2" = "align_koln_official_blocks" ] && '
                '[ "$TEST_REFUSE" = "1" ]; then exit 9; fi\n'
            )
            python.chmod(0o755)
            fake_bash = tools / "bash"
            fake_bash.write_text(
                '#!/bin/sh\necho "regression $*" >> "$TEST_CALLS"\n'
                'exit "$TEST_REGRESSION_EXIT"\n'
            )
            fake_bash.chmod(0o755)
            env = {"PATH": f"{tools}:{os.defpath}", "TEST_CALLS": str(root / "calls"),
                   "TEST_REFUSE": "1" if refuse_alignment else "0",
                   "TEST_REGRESSION_EXIT": str(regression_exit)}
            if enabled:
                env["ALIGN_KOLN_OFFICIAL_BLOCKS"] = "1"
            result = subprocess.run([shutil.which("bash"), str(self.script)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=10)
            return result, (root / "calls").read_text()

    def test_default_skips_topology_and_continues_even_with_custom_geometry(self):
        result, calls = self.run_hook(refuse_alignment=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("align_koln_official_blocks", calls)
        self.assertIn("collectstatic", calls)
        self.assertIn("eigene Geometrie bleibt unverändert", result.stdout)

    def test_explicit_opt_in_runs_alignment_before_collectstatic(self):
        result, calls = self.run_hook(enabled=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(calls.index("align_koln_official_blocks"), calls.index("collectstatic"))
        self.assertIn("--if-present --apply", calls)

    def test_explicit_opt_in_still_fails_closed_on_custom_geometry(self):
        result, calls = self.run_hook(enabled=True, refuse_alignment=True)
        self.assertEqual(result.returncode, 9)
        self.assertIn("align_koln_official_blocks", calls)
        self.assertNotIn("collectstatic", calls)

    def test_regression_timeout_does_not_fail_setup(self):
        result, calls = self.run_hook(regression_exit=124)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("regression scripts/run_regression_v3.sh --seasons 10", calls)
        self.assertIn("Zeitlimit erreicht", result.stderr)

    def test_regression_success_is_reported(self):
        result, calls = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("regression scripts/run_regression_v3.sh --seasons 10", calls)
        self.assertIn("Regressions-Snapshot erstellt", result.stdout)
        self.assertNotIn("WARNUNG", result.stderr)
