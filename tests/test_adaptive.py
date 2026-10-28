import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import reset_notifier as app

NOW = datetime(2026,10,28,12,tzinfo=timezone.utc)
def event(minutes, phase='scheduled'):
    return {'id':'codex-123','phase':phase,'at':(NOW+timedelta(minutes=minutes)).isoformat()}

class AdaptiveTests(unittest.TestCase):
    def test_time_boundaries(self):
        for minutes,seconds in [(90,1200),(40,600),(30,300),(5,300),(0,300),(-55,300),(-59,60),(-60,1200),(-120,1200)]:
            with self.subTest(minutes=minutes):
                self.assertEqual(app.polling_policy([event(minutes)],NOW)['seconds'],seconds)

    def test_completion_cancellation_and_unrelated_completion(self):
        self.assertEqual(app.polling_policy([],NOW)['seconds'],1200)
        self.assertEqual(app.polling_policy([event(0),event(0,'landed')],NOW)['seconds'],1200)
        other=event(0,'landed'); other['id']='codex-456'
        self.assertEqual(app.polling_policy([event(0),other],NOW)['seconds'],300)

    def test_missing_forecast_retained_and_expired(self):
        self.assertEqual(app.polling_policy([],NOW,history=[event(0)])['seconds'],300)
        self.assertEqual(app.polling_policy([],NOW,history=[event(-60)])['seconds'],1200)
        self.assertEqual(app.polling_policy([event(0,'landed')],NOW,history=[event(0)])['seconds'],1200)

    def test_persisted_ledger_forecast_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            with app.Ledger(Path(d)) as ledger:
                app.deliver(ledger,[event(0)],lambda e: self.fail('baseline must not send'))
            with app.Ledger(Path(d)) as ledger:
                app.deliver(ledger,[],lambda e: self.fail('missing forecast must not send'))
                self.assertEqual(app.polling_policy([],NOW,history=[r['latest'] for r in ledger.data['events'].values()])['seconds'],300)

