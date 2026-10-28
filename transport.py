"""Strict fixed-origin transport. Never include exception URLs in logs."""
import json, re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import build_opener, HTTPRedirectHandler, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

class NetworkError(Exception):
    def __init__(self, delay=180): self.delay=delay
class PermanentError(Exception): pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def retry_seconds(value):
    try: return max(180,int(value))
    except (ValueError,TypeError):
        try: return max(180,int((parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()))
        except (ValueError,TypeError,OverflowError): return 180

def webhook_url(value):
    from reset_notifier import Invalid
    if not isinstance(value,str) or not re.fullmatch(r'https://hooks\.slack\.com/services/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+',value):
        raise Invalid('SLACK_WEBHOOK_URL missing or invalid; configure locally')
    return value

def fetch_feed():
    from reset_notifier import API, Invalid
    try:
        with build_opener(NoRedirect()).open(Request(API,headers={'Accept':'application/json','User-Agent':'codex-reset-notifier/1.0'}),timeout=20) as response:
            if response.status!=200 or response.headers.get_content_type()!='application/json': raise Invalid('API HTTP/content type changed')
            body=response.read(2_000_001)
            if len(body)>2_000_000: raise Invalid('API response oversized')
            return json.loads(body)
    except HTTPError as e:
        code=e.code
        delay=retry_seconds(e.headers.get('Retry-After')) if code==429 else 180
        e.close()
        if code==429: raise NetworkError(delay) from None
        if code>=500: raise NetworkError() from None
        raise PermanentError('API permanent HTTP rejection') from None
    except (URLError,TimeoutError,OSError): raise NetworkError() from None
    except (ValueError,UnicodeError): raise Invalid('API invalid JSON') from None

def post_slack(url,payload,*,test_local=False):
    from reset_notifier import Invalid,Halted
    parsed=urlsplit(url)
    local=test_local and parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.username is None and parsed.password is None
    if not local: webhook_url(url)
    request=Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with build_opener(NoRedirect()).open(request,timeout=20) as response:
            if response.status!=200 or response.read(4097)!=b'ok': raise Halted('Slack rejected or ambiguous response')
    except HTTPError as error:
        error.close()
        raise Halted('Slack HTTP rejected; inspect outbox before retry') from None
    except (URLError,TimeoutError,OSError):
        raise Halted('Slack delivery unconfirmed; no automatic resend') from None
