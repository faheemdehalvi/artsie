#!/usr/bin/env python3
"""One CLI request to the shared hub; never owns a native document itself."""
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import artsie

try:
    request = json.load(sys.stdin)
    port = int(os.environ.get("ARTSIE_PORT", "8743"))
    if not 1024 <= port <= 65535:
        raise ValueError("ARTSIE_PORT must be a local unprivileged port")
    if port != 8743:
        # Alternate hubs are explicitly started by the caller, e.g. for isolated
        # verification. Never start a second default service as a fallback.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
            status = json.load(response)
        if status.get("service") != "ARTsie" or status.get("workspace") != str(artsie.WORKSPACE):
            raise ValueError("The alternate port is not this ARTsie workspace")
        artsie.port_default = port
    value = artsie.hub_dispatch(request["action"], request.get("arguments", {}))
    print(json.dumps({"ok": True, "value": value}))
except Exception as error:
    print(json.dumps({"ok": False, "error": str(error)}))
    sys.exit(1)
