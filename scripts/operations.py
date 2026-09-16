#!/usr/bin/env python3
"""Operator-only encrypted backups, verified staged restore, data-retaining stop.
Staged restore never overwrites a running database. references/lifecycle.md gives
the explicit operator procedure for a reviewed in-place restore from that stage.
"""
from __future__ import annotations
import fcntl, json, os, pathlib, re, secrets, sys
from urllib.parse import urlparse
from stacklib import StackError, atom_json, run
from profile_spec import PROFILES
from remote import BASE,STATE,ETC,write
REPO=pathlib.Path('/var/backups/oracle-ai-stack/restic')
PASSWORD=ETC/'restic-password'


def restic(*args,check=True):
    return run(['restic','--repo',str(REPO),'--password-file',str(PASSWORD),*args],timeout=7200,check=check)


def initialize():
    if not (STATE/'managed.json').exists(): raise StackError('Not a managed deployment')
    if not PASSWORD.exists():
        if (REPO/'config').exists(): raise StackError('Existing backup repository has no password file; recover the original key, do not rotate')
        write(PASSWORD,secrets.token_urlsafe(48)+'\n')
    if not (REPO/'config').exists():
        REPO.parent.mkdir(parents=True,exist_ok=True,mode=0o700); restic('init')


def own_volumes():
    files=[(BASE/'compose.proxy.json','oracle-proxy-'),
           (BASE/'compose.gbrain.json','oracle-gbrain-')]; names=set()
    for file,prefix in files:
        if file.exists():
            for key,val in json.loads(file.read_text()).get('volumes',{}).items():
                name=val.get('name',key)
                if not name.startswith(prefix):
                    raise StackError('Unmanaged volume in managed service manifest')
                names.add(name)
    mounts={}
    for name in sorted(names):
        row=json.loads(run(['docker','volume','inspect',name]).stdout)[0]
        path=pathlib.Path(row['Mountpoint']).resolve()
        if path.name!='_data' or path.parent.name!=name: raise StackError('Unexpected Docker volume mountpoint')
        mounts[name]=str(path)
    return mounts


def running_containers():
    values=[]
    for project in ('oracle-proxy','oracle-gbrain'):
        text=run(['docker','ps','-q','--filter','label=com.docker.compose.project='+project]).stdout.decode()
        values.extend(text.split())
    if any(not re.fullmatch('[0-9a-f]{12,64}',v) for v in values): raise StackError('Unexpected container ID')
    return values


def backup():
    initialize(); mounts=own_volumes()
    brain_path=PROFILES['operations'].state/'gbrain/.gbrain/config.json'
    brain=json.loads(brain_path.read_text()) if brain_path.exists() else {}
    if brain.get('engine')=='postgres':
        target=urlparse(brain.get('database_url',''))
        if not (target.scheme in ('postgres','postgresql') and
                target.hostname in ('127.0.0.1','localhost') and target.port==5434 and
                target.path=='/gbrain' and not target.query and not target.fragment and
                'oracle-gbrain-data' in mounts):
            raise StackError('PostgreSQL target has no reviewed managed-volume backup; provide a separate database backup strategy')
    old=running_containers()
    units=[p.unit for p in PROFILES.values()]+['oracle-worker-planning.socket','oracle-worker-development.socket']
    active=[u for u in units if run(['systemctl','is-active','--quiet',u],check=False).returncode==0]
    inflight=run(['systemctl','list-units','--type=service','--state=active','--no-legend','--plain','oracle-worker-*@*.service'],check=False).stdout.decode().strip()
    if inflight:raise StackError('Worker tasks are active; finish or explicitly abort them before backup')
    metadata={'schema':3,'managed':json.loads((STATE/'managed.json').read_text()),'volume_mounts':mounts,
              'consistency':'all managed OpenClaw profiles, proxy and dedicated GBrain PostgreSQL writers stopped before file backup',
              'gbrain_engine':brain.get('engine','not_configured'),
              'offsite_copy':'not provided by local repository alone',
              'retained_legacy_data':'configuration/source files under managed paths are included if present; legacy container volumes are not required or stopped'}
    atom_json(STATE/'backup-inventory.json',metadata)
    paths=[*[str(p.home) for p in PROFILES.values()],str(BASE),str(ETC),str(STATE),*mounts.values(),
           *[ '/etc/systemd/system/'+p.unit for p in PROFILES.values() ],
           *[ '/etc/systemd/system/'+p.unit+'.d' for p in PROFILES.values() ],
           '/etc/systemd/system/oracle-worker-planning.socket','/etc/systemd/system/oracle-worker-development.socket',
           '/etc/systemd/system/oracle-worker-planning@.service','/etc/systemd/system/oracle-worker-development@.service',
           '/etc/systemd/system/oracle-agents.slice','/etc/tmpfiles.d/oracle-ai-stack.conf',
           '/etc/systemd/system/oracle-fetch-egress.service',
           '/etc/sudoers.d/oracle-public-reader']
    paths=[p for p in paths if pathlib.Path(p).exists()]
    try:
        # Stop the ingress first, then workers. The shared lock excludes a task
        # that raced the initial list-units check. No live worker is killed implicitly.
        for u in active:
            if u.endswith('.socket'):run(['systemctl','stop',u])
        guard=open('/run/oracle-ai-stack/worker-exec.lock','r+')
        try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            guard.close();raise StackError('Worker started during quiesce; retry backup after it settles')
        for u in active:
            if u.endswith('.service'):run(['systemctl','stop',u])
        # All managed writers are quiesced before reading database files.
        if old: run(['docker','stop','--time','90',*old],timeout=300)
        output=restic('backup','--tag','one-pass-oci-openclaw-v0.4','--json',*paths)
        summaries=[json.loads(l) for l in output.stdout.decode().splitlines() if l.strip().startswith('{')]
        summary=next((r for r in reversed(summaries) if r.get('message_type')=='summary'),None)
        if not summary or not summary.get('snapshot_id'): raise StackError('restic did not report a snapshot ID')
        restic('check')
        return {'snapshot':summary['snapshot_id'],'repository':str(REPO),'encrypted':True,
                'scope':'Three OpenClaw profile homes including retained PGlite, dedicated GBrain PostgreSQL and proxy TLS volumes, managed source/configuration/state, units and drop-ins, reader policy; legacy container volumes are not included',
                'offsite':'PENDING export to local PC or a separate backup target'}
    finally:
        errors=[]
        # Resume every component, even when one start command raises/times out.
        # A good backup with a stopped service is NOT a successful operation.
        commands=([('containers',['docker','start',*old])] if old else [])
        commands += [(u,['systemctl','start',u]) for u in active]
        if 'guard' in locals() and not guard.closed:guard.close()
        for label,command in commands:
            try:
                if run(command,timeout=300,check=False).returncode: errors.append(label)
            except Exception: errors.append(label)
        atom_json(STATE/'backup-resume.json',{'state':'FAIL' if errors else 'PASS',
                   'components_not_resumed':errors,
                   'snapshot':summary.get('snapshot_id') if 'summary' in locals() and summary else None})
        if errors: raise StackError('Backup maintenance did not resume all components; inspect backup-resume.json locally')


def restore(snapshot,confirmation):
    if not isinstance(snapshot,str) or not re.fullmatch('[0-9a-f]{8,64}',snapshot):
        raise StackError('Choose an explicit snapshot ID; latest/implicit restore is forbidden')
    # Resolve an unambiguous real snapshot before touching a staging directory.
    snapshots=json.loads(restic('snapshots','--json',snapshot).stdout)
    if len(snapshots)!=1: raise StackError('Snapshot did not resolve uniquely')
    sid=snapshots[0]['id']
    if not set(snapshots[0].get('tags',[])) & {'oracle-ai-stack-v0.2','oracle-ai-stack-v0.3','one-pass-oci-opnclaw-v0.4','one-pass-oci-openclaw-v0.4'}: raise StackError('Not a managed stack snapshot')
    target=pathlib.Path('/var/lib/oracle-ai-restore')/sid
    if target.exists(): raise StackError('Restore staging path already exists; inspect it rather than overwrite')
    target.mkdir(parents=True,mode=0o700)
    restic('restore',sid,'--target',str(target),'--verify')
    meta=json.loads((target/'var/lib/oracle-ai-stack/backup-inventory.json').read_text())
    current=json.loads((STATE/'managed.json').read_text())
    if meta['managed']['domain']!=current['domain']: raise StackError('Restored domain differs; cross-server migration review needed')
    return {'state':'RESTORED_AND_VERIFIED_TO_STAGING','snapshot':sid,'staging':str(target),
      'live_data_changed':False,'next':'references/lifecycle.md explicit in-place restore; backup current state first',
      'note':'No destructive live overwrite was performed. This is not a completed live recovery drill.'}


def uninstall(confirmation):
    domain=json.loads((STATE/'managed.json').read_text())['domain']
    if confirmation!='uninstall:'+domain: raise StackError('Explicit confirmation token required: uninstall:<domain>')
    inflight=run(['systemctl','list-units','--type=service','--state=active','--no-legend','--plain','oracle-worker-*@*.service'],check=False).stdout.decode().strip()
    if inflight:raise StackError('Worker tasks still active; no silent termination')
    for unit in ('oracle-worker-planning.socket','oracle-worker-development.socket',*[p.unit for p in PROFILES.values()]):
        run(['systemctl','disable','--now',unit])
    for filename in ('compose.proxy.json','compose.gbrain.json'):
        if (BASE/filename).exists():
            run(['docker','compose','-f',str(BASE/filename),'down'])  # Deliberately no -v.
    # Leave Tailscale, SSH, DNS, firewall, users, all data and restic intact.
    return {'state':'SERVICES_STOPPED_DATA_RETAINED','tailscale':'UNCHANGED','volumes':'RETAINED','oci_instance':'RETAINED_NOT_TERMINATED',
            'credentials':'RETAINED; rotate/revoke explicitly if decommissioning permanently'}


def main():
    if os.geteuid()!=0: raise StackError('Operator/root required')
    action=sys.argv[1]; cfg=json.load(sys.stdin)
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    from operator_lock import locked
    with locked():
        if action=='backup': result=backup()
        elif action=='restore': result=restore(cfg.get('snapshot'),cfg.get('confirmation'))
        elif action=='uninstall': result=uninstall(cfg.get('confirmation'))
        else: raise StackError('Unknown operation')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('OPERATIONS_BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
