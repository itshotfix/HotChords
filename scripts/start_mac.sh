#!/usr/bin/env bash

echo ""
echo "=================================================="
echo "  Starting HotChords..."
echo "=================================================="
echo ""

# ──────────────────────────────────────────────────
#  Navigate to project root
# ──────────────────────────────────────────────────
cd "$(dirname "$0")/.." || { echo "  [ERROR] Could not navigate to project root."; exit 1; }

# ──────────────────────────────────────────────────
#  Check virtual environment
# ──────────────────────────────────────────────────
if [ ! -f "venv/bin/activate" ]; then
    echo "  [ERROR] Virtual environment not found."
    echo ""
    echo "  Please run setup first:"
    echo "    bash scripts/setup_mac.sh"
    echo ""
    exit 1
fi

# ──────────────────────────────────────────────────
#  Activate and launch
# ──────────────────────────────────────────────────
source venv/bin/activate

echo "  The browser will open automatically."
echo "  Press Ctrl+C to stop the server."
echo ""

python3 hotchords.py

if [ $? -ne 0 ]; then
    echo ""
    echo "  [ERROR] HotChords stopped unexpectedly."
    echo ""
    echo "  Common fixes:"
    echo "    1. Run bash scripts/setup_mac.sh to verify dependencies."
    echo "    2. Check if port 5500 is in use: lsof -i :5500"
    echo "    3. See docs/TROUBLESHOOTING.md for more help."
    echo ""
fi
