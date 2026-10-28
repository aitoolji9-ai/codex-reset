import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import cli
import notify
import reset_notifier as a
from test_state import E

class PipelineTest(unittest.TestCase):
    def test_default_output_and_restart(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()) as output:
            send = lambda event: notify.send(a.notification(event))
            with a.Ledger(d) as ledger:
                a.deliver(ledger, [], send)
                a.deliver(ledger, [E], send)
            with a.Ledger(d) as ledger:
                a.deliver(ledger, [E], send)
            messages = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]['id'], E['id'])
            self.assertIn(E['url'], messages[0]['text'])
            self.assertNotIn('blocks', messages[0])

    def test_cli_calls_custom_sender_without_credentials(self):
        now = a.datetime.now(a.timezone.utc).isoformat()
        feed = {'source': 'live', 'generatedAt': now, 'checkedAt': now,
                'events': [], 'watch': {'codex': None}}
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(d) as ledger:
                a.deliver(ledger, [], lambda e: None)
            args = ['cli.py', '--once', '--state-dir', d, '--env-file', str(Path(d)/'missing')]
            with patch('sys.argv', args), patch.object(a, 'fetch_feed', return_value=feed), \
                 patch.object(a, 'parse_feed', return_value=[E]), patch.object(notify, 'send') as sender:
                sender.return_value = None
                self.assertEqual(cli.main(), 0)
                sender.assert_called_once()
                self.assertEqual(sender.call_args.args[0]['phase'], E['phase'])

    def test_sender_failure_blocks_restart(self):
        with tempfile.TemporaryDirectory() as d:
            with a.Ledger(d) as ledger:
                a.deliver(ledger, [], lambda e: None)
                with patch.object(notify, 'send', side_effect=TimeoutError):
                    with self.assertRaises(a.Halted):
                        a.deliver(ledger, [E], lambda e: notify.send(a.notification(e)))
            with a.Ledger(d) as ledger:
                with self.assertRaises(a.Halted):
                    a.deliver(ledger, [E], lambda e: self.fail('duplicate delivery'))
