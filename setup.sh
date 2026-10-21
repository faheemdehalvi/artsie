#!/bin/zsh
# One-shot ARTsie setup on a fresh Mac. Safe to re-run: finished steps are skipped.
set -eu
cd "$(dirname "$0")"

PY="${ARTSIE_PYTHON:-$(command -v python3.14 || command -v python3)}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python 3.12+ required: brew install python@3.14")'
command -v node >/dev/null || { echo "Node 24.10+ required: brew install node"; exit 1; }
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>24||(a===24&&b>=10)?0:1)' \
  || { echo "Node 24.10+ required: brew upgrade node"; exit 1; }

echo "1/4 Python requirements: none (requirements.txt lists no packages; ARTsie uses the standard library)"

echo "2/4 CLI dependencies"
(cd cli && npm ci --ignore-scripts --no-audit --no-fund)

echo "3/4 The 13 ArtCraft apps, CLIs and source snapshots (about 6 GB, checksum-verified)"
"$PY" scripts/install_suite.py

echo "4/4 artsie command in ~/.local/bin"
"$PY" scripts/install_cli.py

echo "Done. Open ARTsie.app or run: ./Start\\ ARTsie.command"
