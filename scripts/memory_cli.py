#!/usr/bin/env python3
"""Operations-only, serialized keyless GBrain CLI. No daemon or cloud key."""
from __future__ import annotations
import argparse, fcntl, json, os, pathlib, pwd, re, sys
from process_guard import ProcessBudgetError, run_bounded
from stacklib import StackError
from profile_spec import get_profile

def command(args,runtime):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}',args.entity) or '..' in args.entity.split('/'):
        raise StackError('Invalid entity key')
    base=[runtime['bun'],runtime['entry']]
    if args.action=='recall': return base+['recall',args.entity,'--json']
    if not args.provenance or not args.text_file: raise StackError('remember requires text-file and provenance')
    p=get_profile('operations');f=args.text_file.resolve()
    if not f.is_relative_to(p.workspace.resolve()): raise StackError('Memory input must be in operations workspace')
    if f.stat().st_size>16000: raise StackError('Memory input too large; save a concise explicit fact')
    text=f.read_text()
    if not text.strip():raise StackError('Empty memory')
    return base+['remember',text,'--entity',args.entity,'--provenance',args.provenance,'--json']

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['remember','recall']);p.add_argument('entity',nargs='?');p.add_argument('--entity',dest='named_entity');p.add_argument('--text-file',type=pathlib.Path);p.add_argument('--provenance');a=p.parse_args()
    a.entity=a.named_entity or a.entity
    if not a.entity:raise StackError('entity required')
    op=get_profile('operations')
    if os.getuid()!=pwd.getpwnam(op.user).pw_uid: raise StackError('Only the operations user owns this memory')
    runtime=json.loads((op.home/'.local/state/oracle-ai-stack/gbrain-runtime.json').read_text())
    env={'HOME':str(op.home),'USER':op.user,'LANG':'C.UTF-8','PATH':str(pathlib.Path(runtime['bun']).parent)+':/usr/bin:/bin','GBRAIN_HOME':runtime['home'],'DO_NOT_TRACK':'1','GBRAIN_PGLITE_WAL_REPAIR':'off'}
    lock=op.home/'.local/state/oracle-ai-stack/gbrain-access.lock'
    with lock.open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as e:raise StackError('Memory store busy; no second PGLite owner started') from e
        try:
            result=run_bounded(command(a,runtime),env=env,timeout=90,
                               max_output=262144,termination_grace=30)
        except ProcessBudgetError as exc:
            raise StackError('Memory operation exceeded its budget; inspect completion before retrying') from exc
    if result.returncode:raise StackError('GBrain call failed; inspect private diagnostics')
    sys.stdout.buffer.write(result.stdout)
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('MEMORY_BLOCKED: '+(str(e) if isinstance(e,StackError) else 'runtime unavailable'),file=sys.stderr);sys.exit(2)
