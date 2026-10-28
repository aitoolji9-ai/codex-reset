"""CLI: Python 3.9+; no third-party runtime dependencies."""
import argparse, json, os, signal, sys, threading, logging
from pathlib import Path
import reset_notifier as app
import notify

log=logging.getLogger('reset-notifier')

def load_env(path):
    if not path.exists(): return
    if path.is_symlink() or path.stat().st_mode & 0o077: raise app.Invalid('.env must be private (chmod 600)')
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,sep,value=line.partition('=')
        if not sep or key not in ('STATE_DIR',): raise app.Invalid('unsupported .env key')
        os.environ.setdefault(key,value.strip().strip('\"\''))

def main():
    parser=argparse.ArgumentParser(description='Codex public reset announcements')
    parser.add_argument('--dry-run',action='store_true',help='read API and validate; never send or change ledger')
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--snapshot',type=Path,help='offline dry-run only')
    parser.add_argument('--env-file',type=Path,default=Path('.env'))
    parser.add_argument('--state-dir',type=Path)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    try:
        if args.snapshot and not args.dry_run: raise app.Invalid('--snapshot requires --dry-run')
        if args.dry_run:
            data=json.loads(args.snapshot.read_text()) if args.snapshot else app.fetch_feed()
            events=app.parse_feed(data)
            print(json.dumps({'dry_run':True,'source':'offline snapshot' if args.snapshot else app.API,'count':len(events),'events':events,'sample_message':app.notification(events[-1]) if events else None},ensure_ascii=False,indent=2))
            return 0
        load_env(args.env_file)
        directory=args.state_dir or Path(os.getenv('STATE_DIR','state'))
        with app.Ledger(directory) as ledger:
            failures=0
            while not stop.is_set():
                delay=1200
                try:
                    data=app.fetch_feed()
                    checked=app.instant(data['checkedAt'])
                    age=(app.datetime.now(app.timezone.utc)-checked).total_seconds()
                    if age < -300 or age > 86400: raise app.Invalid('feed stale or clock skew; check UTC clock')
                    events=app.parse_feed(data)
                    app.deliver(ledger,events,lambda e:notify.send(app.notification(e)))
                    delay=app.polling_policy(events, history=[r['latest'] for r in ledger.data['events'].values()])['seconds']
                    log.info('poll OK; ledger persisted; waiting %ss',delay)
                    failures=0
                except app.NetworkError as e:
                    failures+=1; delay=max(e.delay,min(3600,180*2**min(failures,5)))
                    log.warning('API temporary failure; next attempt in %ss',delay)
                if args.once: return 0 if failures==0 else 3
                stop.wait(delay)
        return 0
    except (app.Invalid,app.Halted,app.PermanentError,OSError,ValueError,KeyError):
        # No raw exception: urllib and OS exceptions can include secrets/paths.
        log.error('STOPPED: configuration/schema/state/delivery needs inspection; no automatic resend')
        return 2

if __name__=='__main__': sys.exit(main())
