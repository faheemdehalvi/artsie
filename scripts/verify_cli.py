#!/usr/bin/env python3
"""Exercise the CLI in its own hub and native sessions, preserving shared documents."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/artsie"


def main():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = "FD-CODE-CLI-QA-" + stamp
    report = {"at": datetime.now(timezone.utc).isoformat(), "isolated_native_sessions": True}
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    code = "import signal,sys,artsie;signal.signal(signal.SIGTERM,lambda *_:sys.exit(0));sys.argv=['artsie.py','serve','--port',sys.argv[1]];artsie.main()"
    stderr = (ROOT / "logs/cli-verification-hub.log").open("a")
    server = subprocess.Popen([sys.executable, "-u", "-c", code, str(port)], cwd=ROOT, stdout=subprocess.PIPE, stderr=stderr, text=True)
    env = {**os.environ, "ARTSIE_PORT": str(port)}

    def cli(*args, succeeds=True):
        process = subprocess.run([str(CLI), *args, "--json", "--full-output"], env=env, capture_output=True, text=True, timeout=175)
        result = json.loads(process.stdout)
        if succeeds:
            assert process.returncode == 0 and result.get("ok") is True, result
            return result["data"]
        assert process.returncode != 0 and result.get("ok") is False, result
        return result

    def native(app, tool, args):
        return cli(app, tool, "--input", json.dumps(args))

    try:
        assert server.stdout and select.select([server.stdout], [], [], 15)[0], "Test hub did not report startup"
        assert "ARTsie ready" in server.stdout.readline()
        apps = cli("apps")["apps"]
        engines = [app for app in apps if app["cli"]]
        assert len(engines) == 13
        report["apps"] = []
        for app in engines:
            tools = cli("tools", app["id"])["tools"]
            assert tools
            report["apps"].append({"app": app["id"], "tools": len(tools)})
        report["total_tools"] = sum(app["tools"] for app in report["apps"])
        cli("call", "photocraft", "tool_that_does_not_exist", succeeds=False)
        cli("call", "filmcraft", "command_run", "--input", "{}", succeeds=False)
        report["invalid_tools_and_arguments_refused"] = True
        original = ROOT / "workspace/Inbox" / (prefix + "-original.png")
        output = ROOT / "workspace/Exports" / (prefix + "-inverted.png")
        native("photocraft", "doc_new", {"name": prefix, "width": 160, "height": 90, "background": "#526246"})
        native("photocraft", "doc_save", {"path": str(original)})
        checksum = hashlib.sha256(original.read_bytes()).hexdigest()
        native("photocraft", "doc_open", {"path": str(original)})
        inspection = native("photocraft", "doc_inspect", {})
        assert inspection.get("content")
        native("photocraft", "command_run", {"id": "image.adjustments.invert", "params": {}})
        native("photocraft", "doc_export", {"path": str(output)})
        assert original.read_bytes()[:8] == output.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert hashlib.sha256(original.read_bytes()).hexdigest() == checksum
        assert original.read_bytes() != output.read_bytes()
        report["photo_edit"] = {"original": str(original), "export": str(output), "original_preserved": True, "state_retained_across_processes": True}
        imported = cli("import", str(original), "--name", prefix + "-import-copy.png")
        assert hashlib.sha256(Path(imported["absolutePath"]).read_bytes()).hexdigest() == checksum
        cli("import", str(original), "--name", prefix + "-import-copy.png", succeeds=False)
        cli("files", "../data", succeeds=False)
        report["import_preserves_original_and_refuses_overwrite"] = True
        project = ROOT / "workspace/Projects" / (prefix + ".fcproj")
        native("filmcraft", "command_run", {"id": "file.newSequence", "params": {"name": prefix, "width": 1280, "height": 720, "fps": 25}})
        native("filmcraft", "command_run", {"id": "file.saveAs", "params": {"path": str(project)}})
        assert project.exists() and project.stat().st_size > 0
        assert native("filmcraft", "sequence_inspect", {}).get("content")
        report["film_project"] = {"path": str(project), "bytes": project.stat().st_size}
        report["passed"] = True
        (ROOT / "data/cli-verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        stderr.close()


if __name__ == "__main__":
    main()
