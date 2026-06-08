#!/usr/bin/env bash
# Dependency security audit script
# Usage: bash scripts/audit_deps.sh
# Run this before every deployment and after any requirements.txt change.
#
# Exits with code 1 if vulnerabilities are found OR if packages are outdated.
# Writes a summary to security-audit.log in the project root.
#
# Requires pip-audit:  pip install pip-audit
# Install once:        pip install pip-audit

set -uo pipefail

REQUIREMENTS="requirements.txt"
REPORT_FILE="security-audit.log"
TIMESTAMP=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
ISSUES_FOUND=0

{
  echo "========================================"
  echo " Security Audit Report"
  echo " $TIMESTAMP"
  echo "========================================"
  echo ""
} | tee "$REPORT_FILE"

# ── Vulnerability scan ────────────────────────────────────────────────────────
{
  echo "=== Vulnerability scan (pip-audit) ==="
} | tee -a "$REPORT_FILE"

if ! command -v pip-audit &>/dev/null; then
    echo "pip-audit not found. Installing..." | tee -a "$REPORT_FILE"
    pip install pip-audit --quiet
fi

set +e
VULN_OUTPUT=$(pip-audit --local 2>&1)
VULN_EXIT=$?
set -e

echo "$VULN_OUTPUT" | tee -a "$REPORT_FILE"

if [ "$VULN_EXIT" -ne 0 ]; then
    ISSUES_FOUND=1
    {
      echo ""
      echo "!! VULNERABILITIES DETECTED — deployment blocked until fixed !!"
    } | tee -a "$REPORT_FILE"
else
    echo "No known vulnerabilities found." | tee -a "$REPORT_FILE"
fi

echo "" | tee -a "$REPORT_FILE"

# ── Outdated packages ─────────────────────────────────────────────────────────
{
  echo "=== Outdated packages ==="
} | tee -a "$REPORT_FILE"

# Nur auf Pakete in requirements.txt prüfen — transitive Abhängigkeiten
# (google-cloud-storage, openai, pydantic_core, tqdm...) nicht blockieren.
REQ_PACKAGES=$(grep -oE '^[a-zA-Z0-9_.-]+' "$REQUIREMENTS")
OUTDATED=$(pip list --outdated --format=columns 2>/dev/null || true)

if [ -z "$OUTDATED" ]; then
    echo "All packages are up to date." | tee -a "$REPORT_FILE"
else
    # Filtere auf Pakete die in requirements.txt stehen
    FILTERED=$(echo "$OUTDATED" | while read -r line; do
        pkg=$(echo "$line" | awk '{print $1}')
        if [ -n "$pkg" ] && echo "$REQ_PACKAGES" | grep -i -w "$pkg" > /dev/null; then
            echo "$line"
        fi
    done)

    if [ -z "$FILTERED" ]; then
        echo "All direct dependencies are up to date." | tee -a "$REPORT_FILE"
    else
        echo "$FILTERED" | tee -a "$REPORT_FILE"
        ISSUES_FOUND=1
        {
          echo ""
          echo "!! OUTDATED PACKAGES DETECTED — review and update $REQUIREMENTS !!"
          echo ""
          echo "To upgrade a package:"
          echo "  1. pip install <package>==<new-version>"
          echo "  2. Update the pinned version in $REQUIREMENTS"
          echo "  3. Run: python manage.py check"
          echo "  4. Run this audit script again to confirm no new CVEs"
        } | tee -a "$REPORT_FILE"
    fi
fi

echo "" | tee -a "$REPORT_FILE"

# ── Final summary ─────────────────────────────────────────────────────────────
if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "✓ Audit passed — no issues found." | tee -a "$REPORT_FILE"
else
    {
      echo "✗ Audit FAILED — see details above."
      echo "  Report saved to: $REPORT_FILE"
    } | tee -a "$REPORT_FILE"
    exit 1
fi
