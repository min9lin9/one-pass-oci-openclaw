#!/usr/bin/env python3
"""Install full gstack for a distinct server-side Codex home, as OpenClaw UID.
This does NOT pretend that installing files proves native Codex/ACP routing.
Codex must discover/configure a supported harness route and run the read-only smoke
from references/gstack.md before reporting gstack_full READY.
"""
import json, os, pathlib, shutil, sys
from remote import BASE,STATE,HOME,PREFIX,user_run,chown_tree
from stacklib import StackError, atom_json

def main():
    if os.geteuid()!=0: raise StackError('Operator-only install')
    lock=json.loads((BASE/'stage/deployment.lock.json').read_text())
    sources=json.loads((HOME/'.local/state/oracle-ai-stack/source-paths.json').read_text())
    hosthome=HOME/'.local/share/oracle-ai-stack/gstack-codex-home'
    user_run('openclaw',['/usr/bin/python3','-c','import pathlib,sys;pathlib.Path(sys.argv[1]).mkdir(parents=True,exist_ok=True,mode=0o700)',hosthome])
    codex_prefix=HOME/'.local/share/oracle-ai-stack/codex-cli'
    # Official package is resolved to exact version during prepare, not @latest per start.
    npm=PREFIX/'tools/node/bin/npm'; codex=codex_prefix/'node_modules/.bin/codex'
    env={'CODEX_HOME':str(hosthome),'GSTACK_HEADLESS':'1','GSTACK_SESSION_KIND':'spawned',
         'DO_NOT_TRACK':'1','DISABLE_TELEMETRY':'1'}
    if not codex.exists():
        user_run('openclaw',[str(npm),'install','--prefix',str(codex_prefix),'--save-exact',
                  '@openai/codex@'+lock['codex_version']],env=env,timeout=1800)
    bunhome=HOME/'.local/share/oracle-ai-stack/bun'
    if not (bunhome/'bin/bun').exists():
        user_run('openclaw',['bash',str(BASE/'stage/core/bun-install.sh')],env=dict(env,BUN_INSTALL=str(bunhome)),timeout=900)
    runtime=HOME/'.local/share/oracle-ai-stack/gstack-full'/pathlib.Path(sources['gstack']).name
    if not runtime.exists():
        user_run('openclaw',['/usr/bin/python3','-c','import shutil,sys;shutil.copytree(sys.argv[1],sys.argv[2])',sources['gstack'],runtime])
    # Upstream setup expects Git metadata. Reconstruct the reviewed snapshot locally,
    # without checking out a branch tip or fetching a different revision.
    if not (runtime/'.git').exists():
        user_run('openclaw',['git','init','-q',str(runtime)])
        user_run('openclaw',['git','-C',str(runtime),'add','.'])
        user_run('openclaw',['git','-C',str(runtime),'-c','user.name=Oracle Stack',
                 '-c','user.email=local@invalid','commit','-qm','Reviewed source snapshot; upstream SHA in receipt'])
    path=str(bunhome/'bin')+':'+str(codex.parent)+':'+str(PREFIX/'tools/node/bin')+':/usr/bin:/bin'
    env['PATH']=path
    if not (runtime/'.oas-host-installed').exists():
        user_run('openclaw',['bash',str(runtime/'setup'),'--host','codex'],env=env,cwd=runtime,timeout=2400)
        from remote import write
        write(runtime/'.oas-host-installed','host setup completed; auth/routing not yet proved\n',user='openclaw')
    user_run('openclaw',[str(codex),'--version'],env=env)
    files=list(hosthome.rglob('SKILL.md'))
    if not files: raise StackError('No generated Codex skills in chosen CODEX_HOME; inspect host adapter output')
    atom_json(STATE/'gstack-full.json',{'source_commit':pathlib.Path(sources['gstack']).name,
       'codex_home':str(hosthome),'codex_binary':str(codex),'skills_found':len(files),
       'state':'INSTALLED_AUTH_AND_DISPATCH_TEST_REQUIRED','note':'No Claude subscription was added; no git push or PR was made.'})
    print('GSTACK_FULL_INSTALLED: native methods remain available; follow gstack.md for authenticated harness route and browser smoke')
if __name__=='__main__':
    try:
        from operator_lock import locked
        with locked(): main()
    except Exception as e: print('GSTACK_FULL_BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
