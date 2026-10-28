import unittest, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
import reset_notifier as a

class HttpTest(unittest.TestCase):
    def test_real_mock_http_sender_and_rejection(self):
        received=[]
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'ok' if len(received)==1 else b'invalid_payload')
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),H)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/mock'
            payload={'text':'mock only','blocks':[]}
            a.post_slack(url,payload,test_local=True)
            with self.assertRaises(a.Halted): a.post_slack(url,payload,test_local=True)
            self.assertEqual(received,[payload,payload])
            with self.assertRaises(a.Invalid): a.post_slack(url,payload)
        finally: server.shutdown();server.server_close();thread.join()
    def test_webhook_url_validation(self):
        for url in ['https://evil.test/services/a/b/c','https://hooks.slack.com.evil.test/services/a/b/c','http://hooks.slack.com/services/a/b/c','https://hooks.slack.com/services/a/b/c?x=1']:
            with self.subTest(url=url),self.assertRaises(a.Invalid): a.webhook_url(url)
    def test_backoff_retry_after(self):
        self.assertEqual(a.retry_seconds('600'),600)
        self.assertGreaterEqual(a.retry_seconds('invalid'),180)
