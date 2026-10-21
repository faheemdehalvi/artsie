#!/usr/bin/env python3
"""Install the maintained ARTsie CLI into the user's command path."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
node = shutil.which("node")
if not node:
    raise SystemExit("Install Node 24.10 or newer before installing the CLI.")
node = str(Path(node).resolve())
if not (ROOT / "cli/node_modules/incur").exists():
    subprocess.run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=ROOT / "cli", check=True)
launcher = ROOT / "bin/artsie"
launcher.write_text("#!/bin/sh\n# ARTsie unified CLI launcher (managed)\nexec " + shlex.quote(node) + " " + shlex.quote(str(ROOT / "cli/src/main.ts")) + ' "$@"\n')
launcher.chmod(0o755)
target = Path.home() / ".local/bin/artsie"
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists() or target.is_symlink():
    if target.resolve() != launcher.resolve():
        raise SystemExit("An unrelated artsie command exists at " + str(target))
else:
    target.symlink_to(launcher)
subprocess.run([str(target), "catalog", "refresh", "--json"], check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"command": str(target), "apps": 13, "catalog": str(ROOT / "config/cli-tools.json")}))
