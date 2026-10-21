#!/usr/bin/env python3
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artsie import native_args

ROOT=Path(__file__).resolve().parents[1]
temporary=tempfile.TemporaryDirectory(prefix='artsie-build-')
bundle=Path(temporary.name)/'ARTsie.app'
(bundle/'Contents/MacOS').mkdir(parents=True,exist_ok=True)
(ROOT/'config/runtime.json').write_text(json.dumps({'python':sys.executable},indent=2))
with (bundle/'Contents/Info.plist').open('wb') as out:
    plistlib.dump(dict(CFBundleName='ARTsie',CFBundleDisplayName='ARTsie',CFBundleIdentifier='local.faheem.artsie',CFBundleExecutable='ARTsie',CFBundlePackageType='APPL',CFBundleShortVersionString='1.0.0',NSHighResolutionCapable=True,NSAppTransportSecurity={'NSAllowsLocalNetworking':True},NSAppleEventsUsageDescription='ARTsie uses the native file picker to copy the files you select into its workspace.'),out)
subprocess.run(['swiftc',str(ROOT/'scripts/ARTsie.swift'),'-O','-o',str(bundle/'Contents/MacOS/ARTsie'),'-framework','AppKit','-framework','WebKit'],check=True)
subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True)
subprocess.run(['ditto','--norsrc','--noextattr',str(bundle),str(ROOT/'ARTsie.app')],check=True)
temporary.cleanup()
config={'mcpServers':{'artsie':{'command':sys.executable,'args':[str(ROOT/'artsie.py'),'mcp']}}}
(ROOT/'config/mcp.json').write_text(json.dumps(config,indent=2))
native={'mcpServers':{a['id']:{'command':str(ROOT/'bin'/(a['id']+'-cli')),'args':native_args(a['id']),'cwd':str(ROOT/'workspace')} for a in json.loads((ROOT/'config/catalog.json').read_text())['apps'] if (ROOT/'bin'/(a['id']+'-cli')).exists()}}
(ROOT/'config/mcp-native-apps.json').write_text(json.dumps(native,indent=2))
if not (ROOT/'.mcp.json').exists():
    (ROOT/'.mcp.json').write_text(json.dumps(config,indent=2))
(ROOT/'.codex').mkdir(exist_ok=True)
project_config=ROOT/'.codex/config.toml'
if not project_config.exists():
    project_config.write_text('[mcp_servers.artsie]\ncommand = '+json.dumps(sys.executable)+'\nargs = '+json.dumps([str(ROOT/'artsie.py'),'mcp'])+'\ncwd = '+json.dumps(str(ROOT))+'\nstartup_timeout_sec = 20\ntool_timeout_sec = 180\n')
print('Built ARTsie.app and MCP configs')
