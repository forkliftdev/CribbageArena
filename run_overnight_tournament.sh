#!/bin/bash
# run_overnight_tournament.sh
# Runs a 7,500-game Grand Tournament across all 6 Cribbage bots in CribbageArena
# with full statistical breakdown across all scoring arenas.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

GAMES="${1:-500}"

echo "======================================================================"
echo " Starting Grand Kribbage Arena Tournament ($GAMES games/matchup)..."
echo "======================================================================"

python3 MegaTournament.py --games "$GAMES"
