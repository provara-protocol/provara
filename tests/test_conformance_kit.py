import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "conformance" / "verify_impl.py"
REF_VAULT = ROOT / "tests" / "fixtures" / "reference_backpack"


class TestConformanceKit(unittest.TestCase):
    def test_reference_backpack_intrinsic_checks(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(VERIFY),
                "--vault",
                str(REF_VAULT),
                "--skip-vectors",
                "--skip-compliance",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        names = {c["name"] for c in payload["checks"]}
        self.assertIn("schema", names)
        self.assertIn("chain_and_signatures", names)
        self.assertIn("reducer_hash", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
