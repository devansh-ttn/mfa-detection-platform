#!/usr/bin/env python3
"""Daily shadow-mode blocklist export helper (MVP-5.1).

Usage:
    ./scripts/shadow/daily_blocklist_export.sh
    API_BASE=http://localhost:8000 ./scripts/shadow/daily_blocklist_export.sh
"""

set -euo pipefail
API_BASE="${API_BASE:-http://localhost:8000}"
OUT_DIR="${OUT_DIR:-./data/shadow}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%d)"
OUT_FILE="$OUT_DIR/blocklist_mfa_high_${STAMP}.json"

curl -s -H "X-MFA-Role: ad_ops" -H "X-MFA-Actor: shadow-export" \
  "${API_BASE}/api/v1/blocklist?tier=MFA_High&limit=1000" \
  -o "$OUT_FILE"

TOTAL="$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d['total'])")"
SHADOW="$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('shadow_mode', 'n/a'))")"
echo "Exported $TOTAL MFA_High entries to $OUT_FILE (shadow_mode=$SHADOW)"
