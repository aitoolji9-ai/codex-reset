import unittest, json, copy, tempfile, threading, subprocess, sys, os, signal, time
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import io
from email.message import Message
import reset_notifier as a
import transport as t
from test_state import E
ROOT=Path(__file__).resolve().parents[1]

class BoundaryTest(unittest.TestCase):
    def test_bad_timestamps_and_urls(self):
        for value in [None,'bad','2026-10-22T10:00:00']:
            with self.subTest(value=value), self.assertRaises(a.Invalid): a.instant(value)
        for value in ['https://evil.test/thsottiaux/status/1','https://x.com/other/status/1','https://x.com/thsottiaux/status/1|injection']:
            with self.subTest(value=value),self.assertRaises(a.Invalid): a.source_url(value)
    def test_schema_duplicate_and_unknown(self):
        data=json.loads((ROOT/'tests'/'fixtures'/'api-live.json').read_text())
        for change in ('duplicate','unknown','nonlive','empty_sources','badtime'):
            d=copy.deepcopy(data)
            if change=='duplicate': d['events'].append(d['events'][0])
            if change=='unknown': d['events'][0]['type']='new_future_type'
            if change=='nonlive': d['source']='cached'
            if change=='empty_sources': d['events'][0]['sources']=[]
            if change=='badtime': d['events'][0]['landedAt']='2026-10-22'
            with self.subTest(change=change),self.assertRaises(a.Invalid): a.parse_feed(d)
    def test_ledger_failure_before_send(self):
        with tempfile.TemporaryDirectory() as d, a.Ledger(d) as s:
            a.deliver(s,[],lambda e:None)
            with patch.object(s,'save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): a.deliver(s,[E],lambda e:self.fail('send before write'))
    def test_success_then_disk_failure_blocks_restart(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(d) as s:
                a.deliver(s,[],lambda e:None)
                original=s.save; n=[0]
                def save():
                    n[0]+=1
                    if n[0]==2: raise OSError('disk full')
                    original()
                with patch.object(s,'save',side_effect=save):
                    with self.assertRaises(OSError): a.deliver(s,[E],lambda e:None)
            with a.Ledger(d) as s:
                self.assertEqual(s.data['events'][E['id']]['status'],'sending')
                with self.assertRaises(a.Halted): a.deliver(s,[E],lambda e:self.fail('duplicate'))
    def test_fresh_banked_and_global_one_each(self):
        with tempfile.TemporaryDirectory() as d,a.Ledger(d) as s:
            a.deliver(s,[],lambda e:None)
            seen=[]; events=[E,dict(E,id='codex-456',kind='Banked Reset')]
            a.deliver(s,events,lambda e:seen.append(a.notification(e)))
            a.deliver(s,events,lambda e:self.fail('duplicate'))
            self.assertEqual(len(seen),2)
    def test_api_http_and_timeout_failures(self):
        for code in (429,503,404,302):
            headers=Message(); headers['Retry-After']='600'
            with self.subTest(code=code),patch.object(t,'build_opener') as opener:
                opener.return_value.open.side_effect=HTTPError(a.API,code,'mock',headers,io.BytesIO())
                with self.assertRaises(t.NetworkError if code in (429,503) else t.PermanentError) as caught: t.fetch_feed()
                if code==429: self.assertEqual(caught.exception.delay,600)
        with patch.object(t,'build_opener') as opener:
            opener.return_value.open.side_effect=URLError('secret must not escape')
            with self.assertRaises(t.NetworkError): t.fetch_feed()
    def test_api_redirect_not_followed(self):
        self.assertIsNone(t.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_cli_sigterm_during_poll_wait(self):
        # Child uses production CLI loop; source read mocked, no external delivery/network.
        with tempfile.TemporaryDirectory() as d:
            env=dict(os.environ,TEST_STATE=d,PYTHONPATH=str(ROOT))
            p=subprocess.Popen([sys.executable,str(ROOT/'tests'/'signal_child.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not (Path(d)/'ledger.json').exists() and p.poll() is None and time.monotonic()<deadline: time.sleep(.02)
                self.assertTrue((Path(d)/'ledger.json').exists())
                p.send_signal(signal.SIGTERM)
                out,err=p.communicate(timeout=3)
                self.assertEqual(p.returncode,0,err)
            finally:
                if p.poll() is None: p.kill();p.communicate()
