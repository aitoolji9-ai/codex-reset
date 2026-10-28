import unittest, tempfile, os
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import io
from email.message import Message
import reset_notifier as a
import transport as t
import cli
from test_state import E
class ThreadTest(unittest.TestCase):
    def test_thread_payload_without_channel_override(self):
        payload=a.blocks(E,thread_ts='1000000000.000001')
        self.assertEqual(payload['thread_ts'],'1000000000.000001')
        self.assertNotIn('channel',payload)
        with self.assertRaises(a.Invalid): a.blocks(E,thread_ts='bad')
    def test_thread_env_file_supported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'.env';p.write_text('SLACK_THREAD_TS=1000000000.000001\n');p.chmod(0o600)
            with patch.dict(os.environ,{},clear=True):
                cli.load_env(p)
                self.assertEqual(os.environ['SLACK_THREAD_TS'],'1000000000.000001')
    def test_http_error_resource_closed(self):
        err=HTTPError(a.API,503,'fixture',Message(),io.BytesIO())
        try:
            with patch.object(err,'close',wraps=err.close) as close,patch.object(t,'build_opener') as opener:
                opener.return_value.open.side_effect=err
                with self.assertRaises(t.NetworkError): t.fetch_feed()
                close.assert_called_once()
        finally: err.close()
