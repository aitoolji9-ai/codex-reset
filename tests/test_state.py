import unittest, tempfile, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import reset_notifier as a
E={'id':'codex-123','kind':'Global Reset','phase':'landed','at':'2026-10-22T10:00:00+00:00','scope':'all','url':'https://x.com/thsottiaux/status/123'}
class StateTest(unittest.TestCase):
    def test_baseline_fresh_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            calls=[]
            with a.Ledger(Path(d)) as store:
                a.deliver(store,[],lambda e:calls.append(e))
                a.deliver(store,[E],lambda e:calls.append(e))
            with a.Ledger(Path(d)) as store:
                a.deliver(store,[E],lambda e:calls.append(e))
                self.assertEqual(store.data['events'][E['id']]['status'],'sent')
            self.assertEqual(len(calls),1)
    def test_first_run_only_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(Path(d)) as s:
                a.deliver(s,[E],lambda e:self.fail('historical send'))
                self.assertEqual(s.data['events'][E['id']]['status'],'baseline')
    def test_uncertain_and_crash_never_retry(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(Path(d)) as s:
                a.deliver(s,[],lambda e:None)
                def fail(e): raise TimeoutError()
                with self.assertRaises(a.Halted): a.deliver(s,[E],fail)
            with a.Ledger(Path(d)) as s:
                with self.assertRaises(a.Halted): a.deliver(s,[E],lambda e:self.fail('retry'))
    def test_lock_and_corrupt_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(Path(d)):
                with self.assertRaises(a.Halted):
                    with a.Ledger(Path(d)): pass
            (Path(d)/'ledger.json').write_text('{')
            with self.assertRaises(a.Halted):
                with a.Ledger(Path(d)): pass
    def test_same_id_update_not_resent(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(Path(d)) as s:
                a.deliver(s,[E],lambda e:None)
                a.deliver(s,[dict(E,phase='scheduled')],lambda e:self.fail('update resent'))
                self.assertEqual(s.data['events'][E['id']]['latest']['phase'],'scheduled')
