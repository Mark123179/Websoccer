#!/usr/bin/env bash
# Dependency security audit script
# Usage: bash scripts/audit_deps.sh
# Run this before every deployment and after any requirements.txt change.
#
# Requires pip-audit:  pip install pip-audit
# Install once:        pip install pip-audit

set -euo pipefail

REQUIREMENTS="requirements.txt"

echo "=== Vulnerability scan (pip-audit) ==="
if ! command -v pip-audit &>/dev/null; then
    echo "pip-audit not found. Installing..."
    pip install pip-audit
fi

pip-audit --local

echo ""
echo "=== Outdated packages ==="
OUTDATED=$(pip list --outdated --format=columns 2>/dev/null || true)
if [ -z "$OUTDATED" ]; then
    echo "All packages are up to date."
else
    echo "$OUTDATED"
    echo ""
    echo "To upgrade a package:"
    echo "  1. pip install <package>==<new-version>"
    echo "  2. Update the pinned version in $REQUIREMENTS"
    echo "  3. Run: python manage.py check"
    echo "  4. Run this audit script again to confirm no new CVEs"
fi

echo ""
echo "Done."
