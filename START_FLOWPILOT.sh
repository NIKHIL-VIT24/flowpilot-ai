#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PYTHON_BIN="$(command -v python3 || command -v python)"
if [ -z "$PYTHON_BIN" ]; then echo "Python 3.11+ is required."; exit 1; fi
if [ ! -x backend/.venv/bin/python ]; then "$PYTHON_BIN" -m venv backend/.venv; fi
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt
if [ ! -f backend/.env ]; then backend/.venv/bin/python -c 'import secrets; open("backend/.env","w").write("SECRET_KEY="+secrets.token_urlsafe(48)+"\nFRONTEND_URL=http://127.0.0.1:8000\n")'; fi
cd backend
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
