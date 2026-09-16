#!/usr/bin/env python3
"""Install canonical GitHub GBrain, memory-only, for operations. Root entry point.
The unrelated npm package named gbrain is never installed. Dependencies are
resolved from the reviewed source lockfile. No identity/cron bootstrap is run.
"""
from __future__ import annotations
import hashlib,json,os,pathlib,re,shutil,uuid
from stacklib import StackError,atom_json,digest_tree,run
from profile_spec import get_profile
from profiles_runtime import as_user,own,write,BASE,STATE

def install(stage,lock):
    if os.geteuid()!=0:raise StackError('Human deployment operator only')
    p=get_profile('operations');src=stage/'aux/gbrain';entry=lock['aux_sources']['gbrain']
    if digest_tree(src)!=entry['sha256']:raise StackError('GBrain reviewed source changed')
    base=p.home/'.local/share/oracle-ai-stack';bun=base/'bun/bin/bun'
    if not bun.exists():as_user(p,['bash',stage/'core/bun-install.sh'],env={'BUN_INSTALL':str(base/'bun')},timeout=600)
    ver=as_user(p,[bun,'--version']).stdout.decode().strip();parts=re.match(r'^(\d+)\.(\d+)\.(\d+)',ver)
    if not parts or tuple(map(int,parts.groups()))<(1,3,11):raise StackError('GBrain requires Bun >=1.3.11')
    dest=base/'gbrain-source'/entry['commit'];receipt=STATE/'gbrain-install.json'
    if not dest.exists():
        as_user(p,['/usr/bin/python3','-c','import shutil,sys;shutil.copytree(sys.argv[1],sys.argv[2])',src,dest],timeout=180)
    marker=dest/'.oas-install-complete'
    env={'BUN_INSTALL':str(base/'bun'),'PATH':str(bun.parent)+':'+str(p.prefix/'tools/node/bin')+':/usr/bin:/bin'}
    if not marker.exists():
        as_user(p,[bun,'install','--frozen-lockfile'],env=env,cwd=dest,timeout=1800)
        write(marker,entry['commit'],p.user)
    home=p.state/'gbrain'
    as_user(p,['/usr/bin/python3','-c','import pathlib,sys;pathlib.Path(sys.argv[1]).mkdir(parents=True,exist_ok=True,mode=0o700)',home])
    env['GBRAIN_HOME']=str(home)
    cli=[bun,dest/'src/cli.ts']
    config_path=home/'.gbrain/config.json'
    if not config_path.exists():as_user(p,cli+['init','--pglite','--no-embedding'],env=env,timeout=600)
    config=json.loads(config_path.read_text())
    if config.get('engine') not in ('pglite','postgres') or config.get('embedding_disabled') is not True:
        raise StackError('Existing GBrain is not a supported memory-only engine; preserve it and review an explicit migration')
    db=config.get('database_path')
    if db and not pathlib.Path(db).expanduser().resolve().is_relative_to(p.home.resolve()):
        raise StackError('GBrain DB lies outside backed-up operations home; review its storage mapping')
    as_user(p,cli+['engine','status','--json'],env=env,timeout=90)
    runtime={'bun':str(bun),'entry':str(dest/'src/cli.ts'),'home':str(home),'mode':'keyless-memory-only','engine':config['engine'],'source_commit':entry['commit']}
    runtimefile=p.home/'.local/state/oracle-ai-stack/gbrain-runtime.json';atom_json(runtimefile,runtime);own(runtimefile.parent,p.user)
    result={'state':'GBRAIN_RUNTIME_INSTALLED','profile':'operations','mode':'keyless-memory-only','engine':config['engine'],'database':str(home),'native_chat_roundtrip':'NOT_TESTED','source_commit':entry['commit']}
    atom_json(receipt,result);return result

def smoke():
    p=get_profile('operations');r=json.loads((p.home/'.local/state/oracle-ai-stack/gbrain-runtime.json').read_text())
    entity='projects/oracle-ai-stack-acceptance';phrase='oracle-memory-'+uuid.uuid4().hex
    env={'GBRAIN_HOME':r['home'],'PATH':str(pathlib.Path(r['bun']).parent)+':/usr/bin:/bin'}
    # Operations gateway is stopped by caller so this smoke has exclusive DB access.
    cli=[r['bun'],r['entry']]
    as_user(p,cli+['remember',phrase,'--entity',entity,'--provenance','explicit installation acceptance test','--json'],env=env)
    read=as_user(p,cli+['recall',entity,'--json'],env=env)
    if phrase not in read.stdout.decode():raise StackError('GBrain independent recall did not return setup marker')
    report={'state':'CLI_REMEMBER_RECALL_PASSED','entity':entity,'marker_sha256':hashlib.sha256(phrase.encode()).hexdigest(),'native_new_conversation':'NOT_TESTED','cleanup':'test fact retained; operator may withdraw via verified GBrain CLI'}
    atom_json(STATE/'gbrain-smoke.json',report);return report
