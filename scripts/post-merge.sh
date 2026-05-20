#!/bin/bash
set -e

python3 manage.py migrate --no-input
python3 manage.py collectstatic --no-input --clear 2>/dev/null || true
