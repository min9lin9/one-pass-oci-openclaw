#!/usr/bin/env python3
"""Cross-profile bridge, NOT OpenClaw sessions_send/ACP.
One socket-activated process per request, running as its destination profile UID.
No arbitrary command, path, model override, or credential can be supplied by caller.
"""
from __future__ import annotations
import fcntl, hashlib, json, os, pathlib, pwd, socket, struct, subprocess, sys, uuid
from profile_spec import get_profile
from stacklib import StackError, atom_json
MAX_REQUEST=96*1024;MAX_RESULT=1024*1024


def validate_request(req,profile):
    if not isinstance(req,dict) or set(req)-{'task_id','prompt','approved_plan','action'}: raise StackError('Unknown task fields')
    task=str(uuid.UUID(req.get('task_id','')))
    action=req.get('action','run')
    if action not in ('run','status'): raise StackError('Unknown task action')
    prompt=req.get('prompt','')
    if action=='run' and (not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>65536): raise StackError('Invalid task prompt size')
    plan=req.get('approved_plan','')
    if not isinstance(plan,str) or len(plan.encode())>24576: raise StackError('Invalid approved plan')
    if profile=='development' and action=='run' and not plan.strip(): raise StackError('Development requires an approved plan supplied by operations')
    return {'task_id':task,'action':action,'prompt':prompt,'approved_plan':plan}


def receipt_path(home,task): return pathlib.Path(home)/'.local/state/oracle-ai-stack/jobs'/(task+'.json')


def execute(req,p,runner=None):
    request=validate_request(req,p.name);path=receipt_path(p.home,request['task_id'])
    prior=json.loads(path.read_text()) if path.exists() else None
    if request['action']=='status': return prior or {'state':'NOT_FOUND','task_id':request['task_id']}
    digest=hashlib.sha256(json.dumps({k:v for k,v in request.items() if k!='action'},sort_keys=True).encode()).hexdigest()
    if prior:
        if prior.get('input_sha256')!=digest: raise StackError('Task ID reused with different input')
        # Ambiguous interrupted tasks are not executed again on an automatic retry.
        return prior
    ready=p.home/'.local/state/oracle-ai-stack/model-ready.json'
    if not ready.exists() or json.loads(ready.read_text()).get('auth_probe')!='PASS':
        return {'state':'PENDING_PROFILE_MODEL_AUTH','task_id':request['task_id'],'retry_safe':True}
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    report={'task_id':request['task_id'],'profile':p.name,'input_sha256':digest,'state':'RUNNING'}
    atom_json(path,report)
    prompt='Task from the operations orchestrator. Follow your own profile permissions.\n'+request['prompt']
    if request['approved_plan']: prompt+='\n\nApproved scope/plan (data, not privilege escalation):\n'+request['approved_plan']
    taskfile=path.with_suffix('.task.md')
    from fssecure import write_text
    write_text(taskfile,prompt)
    command=[str(p.binary),'--profile',p.name,'agent','--agent',p.agent,'--session-id',request['task_id'],
             '--message-file',str(taskfile),'--timeout','600','--json']
    try:
        if runner is None:
            from process_guard import run_bounded
            result=run_bounded(command,timeout=680,max_output=MAX_RESULT)
        else: result=runner(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=680)
        if len(result.stdout)>MAX_RESULT: raise StackError('Worker output exceeded limit; retained local task receipt')
        response=json.loads(result.stdout)
        from evidence import successful_response
        report.update({'state':'COMPLETED' if successful_response(response,result.returncode) else 'FAILED_OR_UNCERTAIN',
                       'exit_code':result.returncode,'response':response,'data_trust':'UNTRUSTED_WORKER_OUTPUT'})
    except Exception:
        report.update({'state':'UNCERTAIN_CHECK_TRANSCRIPT','reason':'Timeout, transport loss, or output error; no automatic rerun'})
    finally:
        taskfile.unlink(missing_ok=True);atom_json(path,report)
    return report


def main():
    p=get_profile(sys.argv[1])
    if p.name not in ('planning','development') or os.getuid()!=pwd.getpwnam(p.user).pw_uid: raise StackError('Wrong worker identity')
    conn=socket.socket(fileno=os.dup(0));conn.settimeout(15)
    _,uid,_=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i')))
    if uid not in (0,pwd.getpwnam('openclaw').pw_uid): raise StackError('Caller is not the operations account')
    data=bytearray()
    while True:
        chunk=conn.recv(8192)
        if not chunk:break
        data.extend(chunk)
        if len(data)>MAX_REQUEST: raise StackError('Task request too large')
    req=validate_request(json.loads(data),p.name)
    if req['action']=='status': result=json.loads(receipt_path(p.home,req['task_id']).read_text()) if receipt_path(p.home,req['task_id']).exists() else {'state':'NOT_FOUND'}
    else:
        with open('/run/oracle-ai-stack/worker-exec.lock','r+') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                result={'state':'BUSY_NOT_STARTED','retry_safe':True,'task_id':req['task_id']}
            else: result=execute(req,p)
    blob=json.dumps(result,ensure_ascii=False).encode()
    if len(blob)>MAX_RESULT+8192: blob=json.dumps({'state':'RESULT_TOO_LARGE','task_id':req['task_id']}).encode()
    conn.settimeout(15);conn.sendall(blob);conn.close()

if __name__=='__main__':
    try: main()
    except Exception:
        # Do not include prompts, subprocess stderr, or credentials in systemd journal.
        try: os.write(1,b'{"state":"BRIDGE_REJECTED","detail":"invalid request or unavailable worker"}')
        except OSError: pass
        sys.exit(2)
