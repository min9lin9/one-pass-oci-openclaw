"""Root installer for three isolated native OpenClaw profiles.
ECC files are reference material only; host-specific model/tool frontmatter and
hooks are NOT imported as executable OpenClaw configuration.
"""
from __future__ import annotations
import grp, hashlib, json, os, pathlib, pwd, re, secrets, subprocess, uuid, datetime
from evidence import exact_marker, selected_model_observed
from process_guard import run_bounded
from stacklib import StackError, atom_json, run
from profile_spec import PROFILES, get_profile, environment, config_for, gateway_unit, auth_mode, provider_for, choose_model
BASE=pathlib.Path('/opt/oracle-ai-stack');STATE=pathlib.Path('/var/lib/oracle-ai-stack');ETC=pathlib.Path('/etc/oracle-ai-stack')


def account(p):
    try: user=pwd.getpwnam(p.user)
    except KeyError:
        run(['useradd','--create-home','--shell','/bin/bash',p.user]);user=pwd.getpwnam(p.user)
    groups={g.gr_name for g in grp.getgrall() if p.user in g.gr_mem or g.gr_gid==user.pw_gid}
    if groups & {'sudo','docker','root'}: raise StackError('Agent account has administrative group membership')
    p.home.chmod(0o700)
    return user


def write(path, content, user=None, mode=0o600):
    from fssecure import write_text, FileSafetyError
    u=pwd.getpwnam(user) if user else None
    try: write_text(path,content,mode=mode,uid=u.pw_uid if u else None,gid=u.pw_gid if u else None)
    except FileSafetyError as exc: raise StackError(str(exc)) from exc


def own(path,user):
    from fssecure import chown_tree as secure_chown, FileSafetyError
    u=pwd.getpwnam(user)
    try: secure_chown(path,u.pw_uid,u.pw_gid)
    except FileSafetyError as exc: raise StackError(str(exc)) from exc


def credentials(p):
    out={}
    if p.env_file.exists():
        import shlex
        for line in p.env_file.read_text().splitlines():
            key,sep,value=line.partition('=')
            if key=='OPENCODE_API_KEY' and sep:
                parsed=shlex.split(value)
                if len(parsed)!=1: raise StackError('Invalid protected model environment file')
                out[key]=parsed[0]
    return out


def as_user(p,args,*,env=None,data=None,timeout=1200,check=True,cwd=None):
    u=pwd.getpwnam(p.user)
    clean=environment(p);clean.update(env or {})
    def demote():
        os.initgroups(p.user,u.pw_gid);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
    try:
        out=run_bounded(list(map(str,args)),input=data,cwd=str(cwd or p.workspace),env=clean,
                           preexec_fn=demote,timeout=timeout)
    except subprocess.TimeoutExpired as e: raise StackError('Profile command timed out; output withheld') from e
    if check and out.returncode: raise StackError('Profile command failed; inspect a private diagnostic, not shared logs')
    return out


def oc(p,*args,check=True,timeout=1200):
    return as_user(p,[p.binary,'--profile',p.name,*args],env=credentials(p),check=check,timeout=timeout)


def invalidate_model(p, reason='AUTH_OR_MODEL_CHANGED'):
    """A previous passing probe never authorizes a new account/model configuration."""
    record={'profile':p.name,'auth_probe':'PENDING','reason':reason,'agent_task':'NOT_TESTED'}
    atom_json(STATE/('model-'+p.name+'.json'),record)
    ready=p.home/'.local/state/oracle-ai-stack/model-ready.json'
    write(ready,json.dumps(record)+'\n',p.user)
    own(ready.parent,p.user)


def save_policy(cfg):
    policy={}
    prior=json.loads((STATE/'profile-auth-policy.json').read_text()) if (STATE/'profile-auth-policy.json').exists() else {}
    for p in PROFILES.values():
        mode=auth_mode(cfg,p.name)
        policy[p.name]={'mode':mode,'provider':provider_for(mode),'requested_model':cfg.get(p.name.upper()+'_MODEL','')}
        current_key=credentials(p).get('OPENCODE_API_KEY','')
        incoming_key=cfg.get('OPENCODE_API_KEY') or current_key
        changed=prior.get(p.name)!=policy[p.name] or (mode!='chatgpt' and incoming_key!=current_key)
        if changed: invalidate_model(p)
        if mode!='chatgpt':
            key=cfg.get('OPENCODE_API_KEY')
            if not key and not current_key: raise StackError('OPENCODE_API_KEY required for selected profile')
            if key:
                if not re.fullmatch(r'[A-Za-z0-9_.:/+=-]+',key): raise StackError('Invalid API key characters; no newline/command interpolation allowed')
                write(p.env_file,'OPENCODE_API_KEY="'+key+'"\n')
        elif p.env_file.exists():
            # No API fallback during subscription mode: preserves deliberate billing choice.
            write(p.env_file,'# ChatGPT OAuth only; no API key injected.\n')
    atom_json(STATE/'profile-auth-policy.json',policy)
    return policy


def install(cfg,stage,lock):
    if os.geteuid()!=0: raise StackError('Profile installation is operator-only')
    for p in PROFILES.values(): account(p)
    try: grp.getgrnam('clawworkers')
    except KeyError: run(['groupadd','--system','clawworkers'])
    for name in ('planning','development'): run(['usermod','-aG','clawworkers',PROFILES[name].user])
    policy=save_policy(cfg)
    for p in PROFILES.values():
        from fssecure import directory
        for d in (p.state,p.workspace,p.prefix):
            with directory(d,create=True): pass
        own(p.state,p.user);own(p.home/'.local',p.user)
        if not p.binary.exists():
            as_user(p,['bash',stage/'core/openclaw-install-cli.sh','--prefix',p.prefix,'--version',lock['openclaw_version'],'--no-onboard'],timeout=2400)
        if lock['openclaw_version'] not in oc(p,'--version').stdout.decode(): raise StackError('Profile runtime differs from reviewed version')
        config=p.state/'openclaw.json'
        if not config.exists():
            generated=config_for(p,cfg,secrets.token_urlsafe(32))
            # No invented model ID. Until auth/catalog/probe passes, no worker
            # job is accepted and Buzz binding is blocked.
            atom_json(config,generated);own(p.state,p.user)
        else:
            old=json.loads(config.read_text())
            if old.get('gateway',{}).get('port')!=p.port or old.get('agents',{}).get('defaults',{}).get('workspace')!=str(p.workspace):
                raise StackError('Existing profile layout conflicts; use explicit migration')
        # Add own role instructions without erasing unrelated user content.
        role=(BASE/'templates/profiles'/p.name/'AGENTS.md').read_text()
        target=p.workspace/'AGENTS.md';receipt=STATE/('role-'+p.name+'.json')
        if target.exists():
            prior=json.loads(receipt.read_text()) if receipt.exists() else {}
            if hashlib.sha256(target.read_bytes()).hexdigest()!=prior.get('sha256'): raise StackError('User modified '+p.name+' role instructions; preserve and review')
        write(target,role,p.user,0o644)
        atom_json(receipt,{'sha256':hashlib.sha256(role.encode()).hexdigest()})
        # Retain original ECC text and license as sources; local adapter defines actual capabilities.
        if p.name!='operations':
            files=['planner.md','architect.md'] if p.name=='planning' else ['tdd-guide.md','code-reviewer.md']
            for name in files:
                src=stage/'aux/ecc/agents'/name
                if not src.exists(): raise StackError('ECC agent layout changed; re-review')
                write(p.workspace/'references/ecc'/name,src.read_text(),p.user,0o644)
            for src in (stage/'aux/ecc').glob('LICENSE*'):
                if src.is_file(): write(p.workspace/'references/ecc'/src.name,src.read_text(),p.user,0o644)
        own(p.state,p.user)
        oc(p,'config','validate')
        write('/etc/systemd/system/'+p.unit,gateway_unit(p),mode=0o644)
    op=PROFILES['operations']
    marker=STATE/'buzz-plugin.json'
    if not marker.exists():
        oc(op,'plugins','install','@openclaw/buzz@'+lock['buzz_plugin_version'])
        atom_json(marker,{'version':lock['buzz_plugin_version'],'profile':'operations'})
    install_worker_units()
    run(['systemctl','daemon-reload'])
    for p in PROFILES.values(): run(['systemctl','enable','--now',p.unit])
    for name in ('planning','development'): run(['systemctl','enable','--now','oracle-worker-'+name+'.socket'])
    atom_json(STATE/'profiles.json',{'schema':3,'profiles':{n:{'user':p.user,'port':p.port,'state':str(p.state),'workspace':str(p.workspace),'unit':p.unit} for n,p in PROFILES.items()},'orchestration':'UNIX_SOCKET_JOB_BRIDGE','live_delegation':'NOT_TESTED'})
    results={}
    for p in PROFILES.values():
        if policy[p.name]['mode']=='chatgpt': results[p.name]='PENDING_CHATGPT_AUTH'
        else:
            try: results[p.name]=configure_one(p,policy[p.name])
            except StackError: results[p.name]='PENDING_API_CATALOG_OR_ENTITLEMENT'
    return {'phase':'THREE_NATIVE_PROFILES_INSTALLED','model_setup':results,'delegation':'NOT_LIVE_TESTED'}


def install_worker_units():
    write('/etc/systemd/system/oracle-agents.slice','[Unit]\nDescription=Shared agent resource ceiling\n[Slice]\nMemoryHigh=6G\nMemoryMax=7G\nTasksMax=1024\n',mode=0o644)
    write('/etc/tmpfiles.d/oracle-ai-stack.conf','d /run/oracle-ai-stack 0755 root root -\nf /run/oracle-ai-stack/worker-exec.lock 0660 root clawworkers -\n',mode=0o644)
    run(['systemd-tmpfiles','--create','/etc/tmpfiles.d/oracle-ai-stack.conf'])
    for name in ('planning','development'):
        p=PROFILES[name]
        socket=f'''[Unit]
Description=Operations to {name} private task socket
[Socket]
ListenStream=/run/oracle-ai-stack/{name}.sock
SocketUser={p.user}
SocketGroup=openclaw
SocketMode=0660
Accept=yes
MaxConnections=4
[Install]
WantedBy=sockets.target
'''
        env='\n'.join('Environment='+k+'='+v for k,v in environment(p).items())
        unit=f'''[Unit]
Description=Restricted {name} task bridge
Requires={p.unit}
After={p.unit}
[Service]
Slice=oracle-agents.slice
User={p.user}
Group={p.user}
SupplementaryGroups=clawworkers
WorkingDirectory={p.workspace}
{env}
EnvironmentFile=-{p.env_file}
ExecStart=/usr/bin/python3 /opt/oracle-ai-stack/scripts/worker_bridge.py {name}
StandardInput=socket
StandardOutput=inherit
StandardError=journal
UMask=0077
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={p.home} /run/oracle-ai-stack/worker-exec.lock
NoNewPrivileges=true
RuntimeMaxSec=780
'''
        write('/etc/systemd/system/oracle-worker-'+name+'.socket',socket,mode=0o644)
        write('/etc/systemd/system/oracle-worker-'+name+'@.service',unit,mode=0o644)


def write_model_receipt(p,record):
    atom_json(STATE/('model-'+p.name+'.json'),record)
    ready=p.home/'.local/state/oracle-ai-stack/model-ready.json'
    write(ready,json.dumps(record)+'\n',p.user);own(ready.parent,p.user)


def configure_one(p,policy):
    # models list does NOT support --agent or --refresh. Refresh is a command.
    with exclusive_profile_state(p):
        invalidate_model(p, 'MODEL_PROBE_PENDING')
        oc(p,'models','refresh','--json',check=False)
        result=oc(p,'models','list','--all','--provider',policy['provider'],'--json')
        data=json.loads(result.stdout);rows=data if isinstance(data,list) else data.get('models',[])
        chosen=choose_model(rows,policy['provider'],policy['requested_model'])
        oc(p,'config','set','agents.defaults.model',json.dumps({'primary':chosen,'fallbacks':[]}))
        oc(p,'config','validate')
        # --check is only auth/runtime metadata health, not successful inference.
        summary=oc(p,'models','status','--agent',p.agent,'--check','--json',check=False)
    record={'profile':p.name,'provider':policy['provider'],'model':chosen,'catalog':'LISTED',
            'auth_metadata':'PASS' if summary.returncode==0 else 'FAIL',
            'auth_probe':'FAIL','agent_task':'NOT_TESTED',
            'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if summary.returncode!=0:
        write_model_receipt(p,record);return record
    # Perform an actual short turn through the configured Gateway; no duplicate
    # embedded owner. This consumes usage and never invokes --deliver.
    marker='oas-model-'+uuid.uuid4().hex
    taskfile=p.workspace/('.model-check-'+uuid.uuid4().hex+'.md')
    write(taskfile,'Installation test. Do not use tools, files, or network. Reply exactly: '+marker,p.user)
    try:
        run(['systemctl','start',p.unit])
        response=oc(p,'agent','--agent',p.agent,'--session-id',str(uuid.uuid4()),
                    '--model',chosen,'--message-file',str(taskfile),'--timeout','60','--json',check=False,timeout=100)
        data=json.loads(response.stdout)
        marker_ok=exact_marker(data,marker,response.returncode)
        model_ok=selected_model_observed(data,policy['provider'],chosen)
        record.update({'auth_probe':'PASS' if marker_ok and model_ok else 'FAIL',
                       'agent_task':'MARKER_PASSED' if marker_ok else 'FAILED_OR_UNKNOWN',
                       'model_identity':'VERIFIED' if model_ok else 'UNVERIFIED'})
    except Exception:
        record['agent_task']='FAILED_OR_UNCERTAIN_NO_AUTOMATIC_RETRY'
    finally:
        taskfile.unlink(missing_ok=True);write_model_receipt(p,record)
    return record


def configure_models(cfg,target=None):
    policy=save_policy(cfg)
    selected=[get_profile(target)] if target else list(PROFILES.values())
    results={}
    for p in selected:
        try: results[p.name]=configure_one(p,policy[p.name])
        except StackError as e: results[p.name]={'state':'PENDING_AUTH_OR_CATALOG','reason':str(e)}
    return results


def profile_status(probe=False):
    policy=json.loads((STATE/'profile-auth-policy.json').read_text()) if (STATE/'profile-auth-policy.json').exists() else {}
    results={}
    for p in PROFILES.values():
        active=run(['systemctl','is-active','--quiet',p.unit],check=False).returncode==0
        record={'gateway':'PASS' if active else 'FAIL','profile':p.name,'user':p.user,'port':p.port,'auth':'NOT_PROBED'}
        if probe and p.binary.exists():
            try:
                result=configure_one(p,policy.get(p.name,{'provider':'openai','requested_model':''}))
                record['auth']=result['auth_probe']
                record['model_identity']=result.get('model_identity','UNVERIFIED')
            except Exception:
                invalidate_model(p,'LIVE_PROBE_FAILED')
                record['auth']='FAIL'
        results[p.name]=record
    return results


from contextlib import contextmanager
@contextmanager
def exclusive_profile_state(p):
    """Stop worker ingress before direct CLI probes/auth, preserving service state.
    Fail if a delegated task is active; never kill it to make a probe succeed.
    """
    import fcntl
    sock='oracle-worker-'+p.name+'.socket'
    socket_active=p.name!='operations' and run(['systemctl','is-active','--quiet',sock],check=False).returncode==0
    gateway_active=run(['systemctl','is-active','--quiet',p.unit],check=False).returncode==0
    guard=None
    try:
        if socket_active:run(['systemctl','stop',sock])
        lock=pathlib.Path('/run/oracle-ai-stack/worker-exec.lock')
        if lock.exists():
            guard=lock.open('r+')
            try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as e:raise StackError('A worker job is active; auth/probe deferred rather than interrupted') from e
        if gateway_active:run(['systemctl','stop',p.unit])
        yield
    finally:
        if guard:guard.close()
        if gateway_active:run(['systemctl','start',p.unit])
        if socket_active:run(['systemctl','start',sock])
