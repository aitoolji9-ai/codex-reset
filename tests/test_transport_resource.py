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
class TransportResourceTest(unittest.TestCase):
    def test_http_error_resource_closed(self):
        err=HTTPError(a.API,503,'fixture',Message(),io.BytesIO())
        try:
            with patch.object(err,'close',wraps=err.close) as close,patch.object(t,'build_opener') as opener:
                opener.return_value.open.side_effect=err
                with self.assertRaises(t.NetworkError): t.fetch_feed()
                close.assert_called_once()
        finally: err.close()
