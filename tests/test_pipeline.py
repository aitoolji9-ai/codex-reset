import unittest, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
import reset_notifier as a
from test_state import E
class PipelineTest(unittest.TestCase):
    def test_real_mock_http_pipeline_restart(self):
        received=[]
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200);self.end_headers();self.wfile.write(b'ok')
            def log_message(self,*args): pass
        http=HTTPServer(('127.0.0.1',0),H)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                send=lambda e:a.post_slack(f'http://127.0.0.1:{http.server_port}/mock',a.blocks(e,thread_ts='1000000000.000001'),test_local=True)
                with a.Ledger(d) as ledger:
                    a.deliver(ledger,[],send)
                    a.deliver(ledger,[E],send)
                    self.assertEqual(ledger.data['events'][E['id']]['status'],'sent')
                with a.Ledger(d) as ledger: a.deliver(ledger,[E],send)
                self.assertEqual(len(received),1)
                self.assertEqual(received[0]['thread_ts'],'1000000000.000001')
                self.assertIn('티보 X 원문',json.dumps(received[0],ensure_ascii=False))
        finally: http.shutdown();http.server_close();thread.join()
