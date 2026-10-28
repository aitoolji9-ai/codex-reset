#!/bin/sh
set -eu
umask 077
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
"$PYTHON" --version
"$PYTHON" -m venv .venv
if [ ! -e .env ]; then cp .env.example .env; fi
chmod 600 .env
mkdir -p state
chmod 700 state
.venv/bin/python -m unittest discover -s tests -v
printf '%s\n' 'Installed locally. Edit .env locally, then: .venv/bin/python cli.py --dry-run' 'Start: .venv/bin/python cli.py ; Ctrl-C to stop. No service auto-start.'
