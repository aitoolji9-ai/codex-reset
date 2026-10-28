import unittest, subprocess, sys, tempfile, json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CliTest(unittest.TestCase):
    def test_snapshot_dryrun_does_not_write_state(self):
        with tempfile.TemporaryDirectory() as d:
            p=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--dry-run','--snapshot',str(ROOT/'tests'/'fixtures'/'api-live.json'),'--state-dir',d],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertTrue(json.loads(p.stdout)['dry_run'])
            self.assertFalse((Path(d)/'ledger.json').exists())
