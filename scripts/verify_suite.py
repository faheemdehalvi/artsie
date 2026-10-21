#!/usr/bin/env python3
"""Integration verification against installed native engines and the stdio gateway."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import artsie

ROOT=artsie.ROOT
def call(app,tool,arguments):
    result=artsie.dispatch('call',dict(app=app,tool=tool,arguments=arguments))
    if result.get('isError'):
        raise AssertionError(result)
    return result

def native_check(app):
    tools=artsie.dispatch('tools',{'app':app['id']})
    assert tools['tools']
    (ROOT/'data'/f'{app["id"]}-tools.json').write_text(json.dumps(tools,indent=2))
    return dict(app=app['name'],version=app['version'],tools=len(tools['tools']))

def main():
    report={'at':datetime.now(timezone.utc).isoformat()}
    report['apps']=list(concurrent.futures.ThreadPoolExecutor(4).map(native_check,[a for a in artsie.catalog()['apps'] if a['cli']]))
    assert len(report['apps'])==13
    print('Native MCP: all 13 apps responded',flush=True)
    # Save an original, reopen it, edit it and export a different file through the gateway.
    source=ROOT/'workspace/Inbox/ARTsie-test-original.png'
    output=ROOT/'workspace/Exports/ARTsie-test-inverted.png'
    call('photocraft','doc_new',{'name':'ARTsie integration check','width':160,'height':90,'background':'#526246'})
    call('photocraft','doc_save',{'path':str(source)})
    original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    call('photocraft','doc_open',{'path':str(source)})
    call('photocraft','command_run',{'id':'image.adjustments.invert','params':{}})
    call('photocraft','doc_export',{'path':str(output)})
    assert source.read_bytes()[:8]==output.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
    assert source.read_bytes()!=output.read_bytes()
    refused=artsie.dispatch('call',{'app':'photocraft','tool':'doc_export','arguments':{'path':str(ROOT/'data/should-not-exist.png')}})
    assert refused.get('isError') and not (ROOT/'data/should-not-exist.png').exists()
    report['photo_edit']={'original':str(source.relative_to(ROOT)),'export':str(output.relative_to(ROOT)),'original_preserved':True,'workspace_boundary_checked':True}
    print('PhotoCraft: open → invert → export, original preserved',flush=True)
    # A real editable video project created and saved by the native engine.
    project=ROOT/'workspace/Projects/ARTsie-test.fcproj'
    call('filmcraft','command_run',{'id':'file.newSequence','params':{'name':'ARTsie test sequence','width':1280,'height':720,'fps':25}})
    call('filmcraft','command_run',{'id':'file.saveAs','params':{'path':str(project)}})
    assert project.exists() and project.stat().st_size>0
    inspected=call('filmcraft','sequence_inspect',{})
    report['film_project']={'path':str(project.relative_to(ROOT)),'inspection':inspected}
    print('FilmCraft: native sequence created, inspected and saved',flush=True)
    for path in ['../data','/etc','Inbox/../../artsie.py']:
        try:
            artsie.workspace_path(path)
        except ValueError:
            continue
        raise AssertionError('Workspace traversal accepted')
    # Actual client-facing MCP process; verify discovery and a proxied native call.
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'ARTsie-verify','version':'1'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/list'},
        {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'artsie_tools','arguments':{'app':'filmcraft'}}},
        {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'artsie_call','arguments':{'app':'filmcraft','tool':'project_inspect','arguments':{}}}}]
    proc=subprocess.run([sys.executable,str(ROOT/'artsie.py'),'mcp'],input='\n'.join(map(json.dumps,requests))+'\n',capture_output=True,text=True,timeout=60)
    replies=[json.loads(l) for l in proc.stdout.splitlines()]
    assert proc.returncode==0 and len(replies)==4 and all('result' in r and not r['result'].get('isError') for r in replies)
    report['gateway_stdio']={'passed':True,'tools':len(replies[1]['result']['tools'])}
    print('Gateway stdio: initialize, discovery and native tool call passed',flush=True)
    (ROOT/'data/verification.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
