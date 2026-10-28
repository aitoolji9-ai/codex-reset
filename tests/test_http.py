import unittest, threading, json
from http.server import BaseHTTPRequestHandler, HTTPServer
import reset_notifier as a

class HttpTest(unittest.TestCase):
    def test_backoff_retry_after(self):
        self.assertEqual(a.retry_seconds('600'),600)
        self.assertGreaterEqual(a.retry_seconds('invalid'),180)
