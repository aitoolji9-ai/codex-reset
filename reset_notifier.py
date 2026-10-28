"""Codex public reset announcements; no account quota inference."""
import re
from datetime import datetime, timezone, timedelta
from transport import post_slack, webhook_url, retry_seconds, fetch_feed, NetworkError, PermanentError

import os, json, fcntl, tempfile, copy
from pathlib import Path

class Halted(Exception): pass

class Ledger:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'ledger.json'
    def __enter__(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink(): raise Halted('state directory symlink')
        os.chmod(self.directory, 0o700)
        self.lock = os.fdopen(os.open(self.directory/'lock', os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600),'a+')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            if self.path.exists():
                if self.path.is_symlink(): raise ValueError()
                self.data=json.loads(self.path.read_text())
                if self.data.get('version')!=1 or not isinstance(self.data.get('initialized'),bool) or not isinstance(self.data.get('events'),dict): raise ValueError()
                for key,record in self.data['events'].items():
                    if not re.fullmatch(r'codex-[0-9]+', key) or record['status'] not in ('baseline','sending','sent','unknown','rejected'): raise ValueError()
                    if not isinstance(record.get('latest'),dict): raise ValueError()
            else: self.data={'version':1,'initialized':False,'events':{}}
            return self
        except Exception:
            self.lock.close()
            raise Halted('state locked, corrupt or unsafe; inspect locally') from None
    def save(self):
        fd,name=tempfile.mkstemp(prefix='.ledger-',dir=self.directory)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(self.data,stream,ensure_ascii=False); stream.flush(); os.fsync(stream.fileno())
            os.replace(name,self.path)
            directory_fd=os.open(self.directory,os.O_RDONLY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        finally:
            if os.path.exists(name): os.unlink(name)
    def __exit__(self,*args): self.lock.close()

def deliver(store, events, send):
    records=store.data['events']
    if any(r['status'] in ('sending','unknown','rejected') for r in records.values()):
        raise Halted('outbox requires manual reconciliation; no automatic resend')
    if not store.data['initialized']:
        store.data['events']={e['id']:{'status':'baseline','latest':e} for e in events}
        store.data['initialized']=True; store.save(); return
    for source_event in events:
        event=dict(source_event)
        prior=records.get(event['id'])
        phases=list(prior.get('phases', [prior['latest']['phase']])) if prior else []
        if prior and (event['phase'] in phases or 'landed' in phases):
            # Historical records have no observed timestamp; do not invent one on restart.
            for field in ('discovered_at','notification_at'):
                if prior['latest'].get(field): event[field]=prior['latest'][field]
            prior['latest']=event
            prior['phases']=phases
            continue
        event['discovered_at']=datetime.now(timezone.utc).isoformat()
        event['notification_at']=datetime.now(timezone.utc).isoformat()
        records[event['id']]={'status':'sending','latest':event,'phases':phases+[event['phase']],
            'first_seen_by_phase':dict((prior or {}).get('first_seen_by_phase',{}),**{event['phase']:event['discovered_at']}),
            'attempted_at':datetime.now(timezone.utc).isoformat()}
        store.save()  # durable intent before external side effect
        try:
            receipt=send(event)
            if receipt is not None: records[event['id']]['receipt']=receipt
        except Exception:
            records[event['id']]['status']='unknown'
            store.save()
            raise Halted('webhook result not confirmed; inspect outbox, no resend') from None
        records[event['id']]['status']='sent'
        records[event['id']]['sent_at']=datetime.now(timezone.utc).isoformat()
        store.save()  # if this fails persisted sending blocks resend
    store.save()

API = 'https://whenreset.dev/api/resets'
class Invalid(Exception): pass

def instant(value):
    if not isinstance(value, str): raise Invalid('timestamp missing')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None: raise ValueError()
        return dt.astimezone(timezone.utc)
    except ValueError: raise Invalid('timestamp must include timezone') from None

def source_url(value):
    if not isinstance(value, str) or not re.fullmatch(r'https://(?:x\.com|twitter\.com)/thsottiaux/status/[0-9]+', value):
        raise Invalid('expected Tibo original post URL')
    return value

def parse_feed(data):
    try:
        if not isinstance(data, dict) or data.get('source') != 'live': raise Invalid('feed not live')
        instant(data['generatedAt']); instant(data['checkedAt'])
        if not isinstance(data['events'], list): raise Invalid('events must be list')
        result = []
        for item in data['events']:
            if item['provider'] != 'codex': continue
            if item['type'] not in ('reset', 'card'): raise Invalid('unknown Codex event type')
            if not re.fullmatch(r'codex-[0-9]+', item['id']): raise Invalid('invalid event id')
            sources = item['sources']
            selected = next((s for s in sources if s['role'] == 'landed'), sources[0])
            result.append(dict(id=item['id'], kind='Global Reset' if item['type']=='reset' else 'Banked Reset',
                phase='landed', at=instant(item['landedAt']).isoformat(), url=source_url(selected['url']), scope=item['scope'],
                api_confirmation=item.get('confirmation'), source_role=selected.get('role')))
        watch = data['watch']['codex']
        if watch is not None:
            if not isinstance(watch.get('open'), bool): raise Invalid('invalid watch open')
            if watch['open']:
                if watch['type'] not in ('reset','card') or not re.fullmatch(r'[0-9]+',watch['postId']): raise Invalid('invalid watch')
                # Same post can remain in watch while already present in the landed ledger.
                # Prefer explicit landed record; never synthesize completion from the clock.
                if not any(e['id']=='codex-'+watch['postId'] for e in result):
                    result.append(dict(id='codex-'+watch['postId'], kind='Global Reset' if watch['type']=='reset' else 'Banked Reset',
                        phase='scheduled', at=instant(watch['scheduledAt']).isoformat(),url=source_url(watch['url']),scope=watch['scope']))
        ids=[e['id'] for e in result]
        if len(ids)!=len(set(ids)): raise Invalid('duplicate event IDs')
        return sorted(result,key=lambda e:(e['at'],e['id']))
    except (KeyError, TypeError, IndexError, AttributeError): raise Invalid('feed schema changed') from None

def polling_policy(events, current=None, history=()):
    """Retain observed forecasts until completion or one hour after scheduled time."""
    remembered = {e['id']: e for e in history}
    remembered.update({e['id']: e for e in events})
    events = list(remembered.values())
    current = current or datetime.now(timezone.utc)
    completed = {e['id'] for e in events if e['phase'] == 'landed'}
    normal = {'seconds': 1200, 'mode': 'normal', 'forecast_id': None}
    for event in events:
        if event['phase'] != 'scheduled' or event['id'] in completed:
            continue
        until = (instant(event['at']) - current).total_seconds()
        if -3600 < until <= 1800:
            return {'seconds': min(300, until + 3600), 'mode': 'near_forecast',
                    'forecast_id': event['id']}
        # Wake at the start of the fast window rather than sleeping past it.
        if until > 1800 and until - 1800 < normal['seconds']:
            normal = {'seconds': until - 1800, 'mode': 'approaching_forecast',
                      'forecast_id': event['id']}
    return normal


def blocks(event, thread_ts=None):
    if thread_ts is not None and not re.fullmatch(r'[0-9]+\.[0-9]{6}',thread_ts):
        raise Invalid('invalid thread timestamp')
    scheduled = event['phase'] == 'scheduled'
    korea = timezone(timedelta(hours=9))
    try:
        at = instant(event['at'])
        at_text = at.astimezone(korea).strftime('%y.%m.%d %H:%M')
    except Invalid:
        at = None
        at_text = '확인 필요'
    try:
        discovered = instant(event.get('discovered_at'))
    except Invalid:
        discovered = None
    uncertain = not at or (not scheduled and discovered and at > discovered)
    title = ('⚠️ Codex 리셋 시각 확인 필요' if uncertain else
             '⏰ Codex 리셋 예정' if scheduled else '✅ Codex 리셋 완료 기록')
    time_label = '예정' if scheduled else '완료 기록'
    kind = {'Global Reset':'사용량 한도 리셋', 'Banked Reset':'리셋권 지급'}.get(event['kind'],event['kind'])
    scope = {'all':'전체', 'paid':'유료 이용자', 'plus_pro_business':'Plus·Pro·Business',
             'affected':'영향받은 이용자', 'unknown':'원문 확인'}.get(event['scope'],'원문 확인')
    lines = [f'{time_label}: {at_text} (한국시간)', f'{kind} · 대상: {scope}']
    if not scheduled:
        if discovered:
            lines.append('발견 시각: '+discovered.astimezone(korea).strftime('%y.%m.%d %H:%M')+' (한국시간)')
            if at and discovered >= at:
                minutes = int((discovered-at).total_seconds() // 60)
                if minutes >= 1:
                    lines.append(f'지연 발견: 완료 기록보다 약 {minutes}분 뒤 확인')
            elif at:
                lines.append('완료 기록의 시각이 미래로 표시돼 확인 필요')
        else:
            lines.append('발견 시각: 미기록 · 지연 확인 필요')
    note = ('예정 안내이며, 완료가 확인되면 별도로 알립니다.' if scheduled else
            'WhenReset 완료 기록 기준 · 내 계정 적용 여부는 확인 필요')
    text = title+'\n'+'\n'.join(lines)
    return {**({'thread_ts':thread_ts} if thread_ts else {}), 'text':text, 'blocks':[
        {'type':'header','text':{'type':'plain_text','text':title}},
        {'type':'section','text':{'type':'plain_text','text':'\n'.join(lines)}},
        {'type':'context','elements':[{'type':'plain_text','text':note}]},
        {'type':'context','elements':[{'type':'mrkdwn','text':f"출처: <https://whenreset.dev|WhenReset> · <{source_url(event['url'])}|티보 X 원문>"}]}]}
