import unittest
import json
import reset_notifier as app

class KoreanMessages(unittest.TestCase):
    def sample(self, phase):
        return dict(id='codex-999',phase=phase,at='2026-10-28T17:00:00Z',
                    discovered_at='2026-10-28T17:16:24Z',kind='Global Reset',scope='all',
                    url='https://x.com/thsottiaux/status/999')
    def test_scheduled_korean_date_rollover(self):
        result=app.notification(self.sample('scheduled'))
        self.assertEqual(result['title'],'⏰ Codex 리셋 예정')
        self.assertIn('26.10.29 02:00 (한국시간)',result['text'])
        self.assertNotIn('완료 기록:',result['text'])
        self.assertNotIn('UTC',json.dumps(result)); self.assertNotIn('전송시도',json.dumps(result,ensure_ascii=False))
    def test_completed_delayed_and_push_preview(self):
        result=app.notification(self.sample('landed'))
        self.assertTrue(result['text'].startswith('✅ Codex 리셋 완료 기록'))
        self.assertIn('약 16분 뒤',result['text'])
        self.assertIn('26.10.29 02:16',result['text'])
        self.assertIn('내 계정 적용',result['text'])
        self.assertEqual(result['sources'][1]['url'], self.sample('landed')['url'])
    def test_future_completion_not_success_title(self):
        e=self.sample('landed');e['at']='2099-01-01T00:00:00Z'
        self.assertTrue(app.notification(e)['text'].startswith('⚠️'))
