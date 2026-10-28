import os, sys
from unittest.mock import patch
import cli
from datetime import datetime,timezone
sys.argv=['cli.py','--state-dir',os.environ['TEST_STATE'],'--env-file','/nonexistent-fixture-env']
os.environ['SLACK_WEBHOOK_URL']='https://hooks.slack.com/services/mock/mock/mock'
now=datetime.now(timezone.utc).isoformat()
feed={'source':'live','generatedAt':now,'checkedAt':now,'events':[],'watch':{'codex':None}}
with patch.object(cli.app,'fetch_feed',return_value=feed),patch.object(cli.app,'post_slack',side_effect=AssertionError('external send forbidden')):
    sys.exit(cli.main())
