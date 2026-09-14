#!/usr/bin/env python3
"""Local Codex operator CLI. Preparing/plan needs no Oracle credentials.
All server mutations are explicit actions. Secrets travel only via stdin over SSH.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, pathlib, re, shlex, shutil, subprocess, sys, tarfile, tempfile, urllib.parse, urllib.request
from stacklib import StackError, atom_json, cf_request, digest_tree, domain_name, load_env, require, run, tailnet_ipv4
from extensions import stage as stage_extensions, snapshot, verify_stage, seal
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HOME=pathlib.Path.home()/'.config/oracle-ai-stack'


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'oracle-ai-stack/0.3'}),timeout=45) as r:
        return json.load(r)


def download(url,path):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'oracle-ai-stack/0.3'}),timeout=45) as r:
        data=r.read(10*1024*1024+1)
    if len(data)>10*1024*1024: raise StackError('Bootstrap resource exceeds size limit')
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data); path.chmod(0o644)
    return hashlib.sha256(data).hexdigest()


def npm_version(name):
    meta=get_json('https://registry.npmjs.org/'+urllib.parse.quote(name,safe='')+'/latest')
    v=meta.get('version','')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?',v): raise StackError('No exact package version resolved')
    return {'version':v,'integrity':meta.get('dist',{}).get('integrity','')}


def prepare(where):
    stage_extensions(ROOT/'manifests/extensions.json',where)
    print('STAGING infrastructure sources (no installation scripts executed)',flush=True)
    buzz=snapshot('block/buzz','main',where/'core/buzz')
    cf=snapshot('caddy-dns/cloudflare','master',where/'core/caddy-dns-cloudflare')
    bootstrap={}
    for name,url in [('openclaw-install-cli.sh','https://openclaw.ai/install-cli.sh'),
                     ('tailscale-install.sh','https://tailscale.com/install.sh'),
                     ('bun-install.sh','https://bun.sh/install')]:
        bootstrap[name]={'url':url,'sha256':download(url,where/'core'/name)}
    aux={}
    for source in json.loads((ROOT/'manifests/bootstrap-sources.json').read_text())['sources']:
        sid=source['id']; dest=where/'aux'/sid
        commit=snapshot(source['repo'],source['ref'],dest)
        aux[sid]={'repo':source['repo'],'commit':commit,'sha256':digest_tree(dest)}
    sdk=get_json('https://pypi.org/pypi/oci/json')['info']['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',sdk): raise StackError('Invalid OCI SDK version')
    oc=npm_version('openclaw'); bp=npm_version('@openclaw/buzz'); codex=npm_version('@openai/codex')
    lock={'schema':3,'aux_sources':aux,'oci_sdk_version':sdk,'buzz_commit':buzz,'buzz_tree_sha256':digest_tree(where/'core/buzz'),
      'caddy_dns_commit':cf,'caddy_tree_sha256':digest_tree(where/'core/caddy-dns-cloudflare'),
      'openclaw_version':oc['version'],'openclaw_npm_integrity':oc['integrity'],
      'buzz_plugin_version':bp['version'],'buzz_plugin_npm_integrity':bp['integrity'],
      'codex_version':codex['version'],'bootstrap':bootstrap}
    atom_json(where/'deployment.lock.json',lock)
    print('PREPARED_NOT_REVIEWED; inspect selected code and bootstrap files, then seal with review notes')


def verify_core(where):
    lock=json.loads((where/'deployment.lock.json').read_text())
    for name,entry in lock['bootstrap'].items():
        if hashlib.sha256((where/'core'/name).read_bytes()).hexdigest()!=entry['sha256']:
            raise StackError('Bootstrap script changed after preparation')
    if digest_tree(where/'core/buzz')!=lock['buzz_tree_sha256']: raise StackError('Buzz source changed')
    if digest_tree(where/'core/caddy-dns-cloudflare')!=lock['caddy_tree_sha256']: raise StackError('Caddy plugin source changed')
    if lock.get('schema')!=3: raise StackError('Re-prepare sources for v0.3; do not reuse a v0.2 review receipt')
    expected={'oci-instance-creator','gbrain','ecc'}
    if set(lock.get('aux_sources',{}))!=expected:raise StackError('Missing bootstrap/profile sources')
    for sid,entry in lock['aux_sources'].items():
        if digest_tree(where/'aux'/sid)!=entry['sha256']:raise StackError('Auxiliary reviewed source changed: '+sid)
    return lock


def seal_all(where,notes):
    verify_core(where); seal(where,notes)
    receipt=json.loads((where/'review.receipt.json').read_text())
    receipt['deployment_lock_sha256']=hashlib.sha256((where/'deployment.lock.json').read_bytes()).hexdigest()
    atom_json(where/'review.receipt.json',receipt)
    print('CORE_AND_EXTENSION_REVIEW_RECEIPT_WRITTEN')


def verify_all(where):
    verify_stage(where); verify_core(where)
    rec=json.loads((where/'review.receipt.json').read_text())
    if rec.get('deployment_lock_sha256')!=hashlib.sha256((where/'deployment.lock.json').read_bytes()).hexdigest():
        raise StackError('Core review receipt missing/stale')


def ssh_args(cfg):
    require(cfg,'ORACLE_HOST','ORACLE_SSH_USER','ORACLE_SSH_KEY')
    key=pathlib.Path(cfg['ORACLE_SSH_KEY']).expanduser()
    if not key.is_file(): raise StackError('SSH key file missing')
    args=['ssh','-i',str(key),'-p',cfg['SSH_PORT'],'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
          '-o','ConnectTimeout=15','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']
    if cfg.get('SSH_KNOWN_HOSTS'): args+=['-o','UserKnownHostsFile='+str(pathlib.Path(cfg['SSH_KNOWN_HOSTS']).expanduser())]
    return args+[cfg['ORACLE_SSH_USER']+'@'+cfg['ORACLE_HOST']]


def ssh(cfg,command,data=None,timeout=3600,check=True):
    return run(ssh_args(cfg)+[command],data=data,timeout=timeout,check=check)


def remote(cfg,action,extra=None,probe=False):
    payload={k:cfg[k] for k in ('DOMAIN','CLOUDFLARE_API_TOKEN','CLOUDFLARE_DNS01_TOKEN',
             'TAILSCALE_AUTH_KEY','OPENCLAW_MODEL','BUZZ_ROOM_ID','BUZZ_OWNER_PUBKEY',
             'OPENCODE_API_KEY','OPENCODE_CATALOG','OPERATIONS_AUTH','PLANNING_AUTH','DEVELOPMENT_AUTH',
             'OPERATIONS_MODEL','PLANNING_MODEL','DEVELOPMENT_MODEL') if cfg.get(k)}
    payload.update(extra or {})
    # SSH_CONNECTION is explicitly preserved, not arbitrary agent/client environment.
    cmd='sudo -n --preserve-env=SSH_CONNECTION python3 /opt/oracle-ai-stack/scripts/remote.py '+action
    if probe: cmd+=' --probe'
    p=ssh(cfg,cmd,json.dumps(payload).encode())
    lines=p.stdout.decode().strip().splitlines()
    if not lines: raise StackError('Remote worker returned no receipt')
    return json.loads(lines[-1])


def trust_host(cfg,fingerprint):
    require(cfg,'ORACLE_HOST')
    if not fingerprint.startswith('SHA256:'): raise StackError('Provide a SHA256 host-key fingerprint verified independently')
    scan=run(['ssh-keyscan','-T','10','-p',cfg['SSH_PORT'],cfg['ORACLE_HOST']],check=False).stdout
    matches=[]
    for line in scan.splitlines():
        if line.startswith(b'#'): continue
        with tempfile.NamedTemporaryFile() as f:
            f.write(line+b'\n'); f.flush()
            value=run(['ssh-keygen','-lf',f.name],check=False).stdout.decode().split()
        if len(value)>1 and value[1]==fingerprint: matches.append(line)
    if not matches: raise StackError('Scanned host key does not match independently verified fingerprint')
    p=pathlib.Path(cfg.get('SSH_KNOWN_HOSTS') or str(pathlib.Path.home()/'.ssh/known_hosts')).expanduser()
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with p.open('ab') as f:
        for line in matches: f.write(line+b'\n')
    p.chmod(0o600); print('VERIFIED_HOST_KEY_ENROLLED')


def cloudflare_zone(cfg):
    require(cfg,'DOMAIN','CLOUDFLARE_API_TOKEN')
    domain=domain_name(cfg['DOMAIN'])
    result=cf_request(cfg['CLOUDFLARE_API_TOKEN'],'GET','/zones?'+urllib.parse.urlencode({'name':domain,'status':'active'}))['result']
    if len(result)!=1: raise StackError('Expected exactly one accessible active zone for DOMAIN')
    return result[0]['id']


def dns_plan(cfg,zone,ip):
    ip=tailnet_ipv4(ip); actions=[]
    for sub in ('buzz','openclaw'):
        name=sub+'.'+cfg['DOMAIN']
        records=cf_request(cfg['CLOUDFLARE_API_TOKEN'],'GET',f'/zones/{zone}/dns_records?'+urllib.parse.urlencode({'name':name}))['result']
        conflicts=[r for r in records if r['type'] in ('A','AAAA','CNAME')]
        payload={'type':'A','name':name,'content':ip,'ttl':300,'proxied':False,
                 'comment':'managed-by:oracle-ai-stack-v0.2'}
        if not conflicts: actions.append(('POST',f'/zones/{zone}/dns_records',payload))
        elif len(conflicts)==1 and conflicts[0]['type']=='A':
            r=conflicts[0]
            if r.get('content')==ip and not r.get('proxied'): continue
            if r.get('comment')!='managed-by:oracle-ai-stack-v0.2':
                raise StackError('Existing DNS differs and is unmanaged: '+name+'; explicit migration required')
            actions.append(('PUT',f'/zones/{zone}/dns_records/{r["id"]}',payload))
        else: raise StackError('Conflicting A/AAAA/CNAME records: '+name+'; no records overwritten')
    return actions


def upload(cfg,where):
    verify_all(where)
    # Read-only validation occurs BEFORE copying even a single root worker file.
    script=(ROOT/'scripts/target_preflight.py').read_text()
    ssh(cfg,'sudo -n python3 -c '+shlex.quote(script),json.dumps({'domain':cfg['DOMAIN']}).encode(),timeout=60)
    # Stage contains PUBLIC sources only. No secrets file is part of this archive.
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as tf:
        for name in ('scripts','adapters','manifests','references','templates','SKILL.md','README.md'):
            tf.add(ROOT/name,arcname=name,filter=tar_filter)
        tf.add(where,arcname='stage',filter=tar_filter)
    temp=ssh(cfg,'sudo -n mktemp -d /opt/oracle-ai-upload.XXXXXXXX').stdout.decode().strip()
    if not re.fullmatch(r'/opt/oracle-ai-upload\.[A-Za-z0-9]+',temp): raise StackError('Invalid remote staging directory')
    try:
        ssh(cfg,'sudo -n tar -xzf - --no-same-owner -C '+temp,buf.getvalue())
        # Preserve installed data. Only worker code and the reviewed staging area change.
        cmd=f'''set -eu
sudo -n mkdir -p /opt/oracle-ai-stack
for d in scripts adapters manifests references templates; do
  sudo -n mkdir -p /opt/oracle-ai-stack/$d
  sudo -n cp -a {temp}/$d/. /opt/oracle-ai-stack/$d/
done
if sudo -n test -e /opt/oracle-ai-stack/stage; then
  old=$(sudo -n mktemp -d /opt/oracle-ai-stage.previous.XXXXXXXX)
  sudo -n mv /opt/oracle-ai-stack/stage \"$old/stage\"
fi
sudo -n mv {temp}/stage /opt/oracle-ai-stack/stage
sudo -n find /opt/oracle-ai-stack/stage -type d -exec chmod 755 {{}} +
sudo -n find /opt/oracle-ai-stack/stage -type f -exec chmod a+r {{}} +
sudo -n chmod 755 /opt/oracle-ai-stack /opt/oracle-ai-stack/scripts
'''
        guarded="import subprocess,sys;sys.path.insert(0,"+repr(temp+'/scripts')+");from operator_lock import locked;from target_preflight import validate;\nwith locked():\n validate("+repr({'domain':'PLACEHOLDER'})+");subprocess.run(['bash','-c',"+repr(cmd)+"],check=True)"
        guarded=guarded.replace(repr({'domain':'PLACEHOLDER'}),repr({'domain':cfg['DOMAIN']}))
        ssh(cfg,'sudo -n python3 -c '+shlex.quote(guarded))
    finally:
        ssh(cfg,'sudo -n rm -rf -- '+temp,check=False)


def tar_filter(info):
    if '__pycache__' in pathlib.PurePosixPath(info.name).parts or info.name.endswith('.pyc'): return None
    if pathlib.PurePosixPath(info.name).name=='review-notes.md': return None
    if not (info.isfile() or info.isdir()): raise StackError('Bundle contains an unexpected link or special file')
    return info


def setup(cfg,where,local_state):
    require(cfg,'DOMAIN','CLOUDFLARE_API_TOKEN')
    verify_all(where)
    zone=cloudflare_zone(cfg)  # BEFORE server mutation
    if not cfg.get('ORACLE_HOST'):
        cfg=provision_local(cfg,where,local_state)
    ssh(cfg,'sudo -n cloud-init status --wait',timeout=900)
    ssh(cfg,'sudo -n true')    # already authorized bootstrap SSH/sudo must work
    upload(cfg,where)
    print('CONFIGURING_HOST',flush=True)
    host=remote(cfg,'host'); ip=tailnet_ipv4(host['tailscale_ip'])
    actions=dns_plan(cfg,zone,ip)  # validate both hosts before writes
    for method,path,body in actions: cf_request(cfg['CLOUDFLARE_API_TOKEN'],method,path,body)
    print('DNS_CONFIGURED_PRIVATE_IP',flush=True)
    for phase in ('buzz','openclaw','proxy','extensions','gbrain'):
        print('CONFIGURING_'+phase.upper(),flush=True)
        receipt=remote(cfg,phase)
        atom_json(local_state/(phase+'.json'),receipt)
    # Export owner identity directly to a protected local file, never chat/stdout.
    owner=remote(cfg,'identities')
    atom_json(local_state/'buzz-owner.secret.json',owner)
    if cfg.get('BUZZ_ROOM_ID'): atom_json(local_state/'buzz-bind.json',remote(cfg,'bind-buzz'))
    result=remote(cfg,'status'); atom_json(local_state/'status.json',result)
    star_prompt_repo()
    print(json.dumps({'state':'INSTALLED_PENDING_ACCEPTANCE','report':str(local_state/'status.json'),
      'next':['ChatGPT OAuth for selected profiles, then models --probe','Buzz owner/room Bot-role approval','gstack full host setup',
              'operations -> planning -> development task roundtrip','GBrain new-conversation recall',
              'TLS and actual Buzz message roundtrip','encrypted backup export and restore drill']},ensure_ascii=False,indent=2))


def hydrate_handoff(cfg,local_state):
    path=local_state/'oci-handoff.json'
    if cfg.get('ORACLE_HOST') or not path.exists():return cfg
    from stacklib import private_file
    private_file(path)
    saved=json.loads(path.read_text());merged=dict(cfg)
    for key in ('DOMAIN','OCI_TENANCY','OCI_REGION'):
        if cfg.get(key) and cfg[key]!=saved.get(key):raise StackError('OCI handoff belongs to another deployment; use a separate --state directory')
    for key in ('ORACLE_HOST','ORACLE_SSH_USER','ORACLE_SSH_KEY','SSH_PORT'):
        if saved.get(key):merged[key]=saved[key]
    merged['SSH_KNOWN_HOSTS']=str(local_state/'known_hosts')
    if not (local_state/'known_hosts').exists():
        trust_host(merged,saved['SSH_FINGERPRINT'])
    return merged


def provision_local(cfg,where,local_state,plan_only=False):
    verify_all(where)
    lock=verify_core(where)
    # SDK installed only on the personal computer. No API key enters an archive/VM.
    venv=local_state/'oci-sdk-venv';python=venv/'bin/python'
    if not python.exists():run([sys.executable,'-m','venv',str(venv)],timeout=180)
    wanted=lock['oci_sdk_version'];marker=venv/'sdk-version.json'
    if not marker.exists() or json.loads(marker.read_text()).get('version')!=wanted:
        run([str(python),'-m','pip','install','oci=='+wanted],timeout=900)
        freeze=run([str(python),'-m','pip','freeze']).stdout.decode()
        atom_json(marker,{'version':wanted,'resolved_dependencies':freeze.splitlines()})
    payload=json.dumps(cfg).encode()
    out=run([str(python),str(ROOT/'scripts/oci_provision.py'),'plan' if plan_only else 'provision','--state',str(local_state)],data=payload,timeout=2400,check=False)
    if out.returncode:
        # Child emits a sanitized structured reason rather than raw SDK exceptions.
        try: message=json.loads(out.stderr.decode().strip().splitlines()[-1])['message']
        except Exception:message='OCI provisioning blocked; inspect private local state'
        raise StackError(message)
    result=json.loads(out.stdout.decode().strip().splitlines()[-1])
    if plan_only:return result
    merged=hydrate_handoff({k:v for k,v in cfg.items() if k!='ORACLE_HOST'},local_state)
    handoff=json.loads((local_state/'oci-handoff.json').read_text())
    merged['SSH_KNOWN_HOSTS']=str(local_state/'known_hosts')
    trust_host(merged,handoff['SSH_FINGERPRINT'])
    return merged


def star_prompt_repo():
    if not shutil.which('gh') or run(['gh','auth','status'],check=False).returncode:
        print('STAR_PENDING: local GitHub CLI authentication not available'); return False
    repo='min9lin9/prompt-engineering-skills'
    p=run(['gh','api','--method','PUT','/user/starred/'+repo],check=False)
    verify=run(['gh','api','/user/starred/'+repo],check=False) if p.returncode==0 else p
    print('STAR_CONFIRMED: '+repo if verify.returncode==0 else 'STAR_PENDING: authenticated user lacks required access')
    return verify.returncode==0


def discover(out):
    p=run(['gh','repo','list','min9lin9','--limit','1000','--json','nameWithOwner,isPrivate,isArchived,description,url'])
    repos=json.loads(p.stdout)
    # Do not leak private repo metadata into a redistributable catalog.
    public=[r for r in repos if not r.get('isPrivate')]
    atom_json(out,{'repositories':public,'private_metadata_omitted':True,
                  'instruction':'Metadata only. Read code and license before extending the manifest. No automatic execution.'})
    print('PUBLIC_REPOSITORY_INVENTORY_WRITTEN: '+str(out))


def lifecycle(cfg,action,snapshot_id=None,confirm=None):
    payload={'snapshot':snapshot_id,'confirmation':confirm}
    p=ssh(cfg,'sudo -n python3 /opt/oracle-ai-stack/scripts/operations.py '+action,json.dumps(payload).encode(),timeout=7200)
    print(p.stdout.decode())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','prepare','seal','verify-sources','discover','trust-host','setup','status','repair','oauth',
                    'bind-buzz','gstack-full','gbrain','memory-smoke','provision','oci-plan','models','profiles','acceptance','backup','restore','uninstall','update','star'])
    p.add_argument('--secrets',type=pathlib.Path,default=DEFAULT_HOME/'secrets.env')
    p.add_argument('--stage',type=pathlib.Path,default=DEFAULT_HOME/'stage')
    p.add_argument('--state',type=pathlib.Path,default=DEFAULT_HOME/'state')
    p.add_argument('--review-notes',type=pathlib.Path)
    p.add_argument('--fingerprint'); p.add_argument('--snapshot'); p.add_argument('--confirm')
    p.add_argument('--profile',choices=['operations','planning','development']); p.add_argument('--probe',action='store_true'); a=p.parse_args()
    if a.action=='plan':
        print(json.dumps({'extensions':json.loads((ROOT/'manifests/extensions.json').read_text()),'bootstrap':json.loads((ROOT/'manifests/bootstrap-sources.json').read_text())},indent=2)); return
    if a.action=='prepare': prepare(a.stage); return
    if a.action=='seal':
        if not a.review_notes: p.error('--review-notes required')
        seal_all(a.stage,a.review_notes); return
    if a.action=='verify-sources': verify_all(a.stage); print('ALL_SOURCE_HASHES_OK'); return
    if a.action=='discover': discover(a.state/'public-repositories.json'); return
    if a.action=='star': star_prompt_repo(); return
    cfg=hydrate_handoff(load_env(a.secrets),a.state)
    if a.action in ('provision','oci-plan'):
        value=provision_local(cfg,a.stage,a.state,plan_only=a.action=='oci-plan')
        print(json.dumps(value if a.action=='oci-plan' else {'state':'INSTANCE_READY','handoff':str(a.state/'oci-handoff.json')},indent=2))
    elif a.action=='trust-host':
        if not a.fingerprint: p.error('--fingerprint required')
        trust_host(cfg,a.fingerprint)
    elif a.action in ('setup','repair'):
        # Repair reuses exact reviewed versions; no update/reset/delete of user content.
        setup(cfg,a.stage,a.state)
    elif a.action=='status':
        value=remote(cfg,'status',probe=a.probe); atom_json(a.state/'status.json',value)
        print(json.dumps(value,indent=2));
        if value['overall']!='READY': sys.exit(3)
    elif a.action=='bind-buzz': print(json.dumps(remote(cfg,'bind-buzz'),indent=2))
    elif a.action in ('models','profiles','gbrain','memory-smoke','acceptance'):
        value=remote(cfg,a.action,{'profile':a.profile} if a.profile else {},probe=a.probe)
        atom_json(a.state/(a.action+'.json'),value);print(json.dumps(value,indent=2))
    elif a.action=='oauth':
        # Interactive user terminal, not a token copied from local Codex auth.json.
        selected=a.profile or 'operations'
        cmd='sudo -n python3 /opt/oracle-ai-stack/scripts/profile_admin.py oauth --profile '+selected
        args=ssh_args(cfg); args.insert(-1,'-t')
        code=subprocess.call(args+[cmd]); sys.exit(code)
    elif a.action=='gstack-full':
        p=ssh(cfg,'sudo -n python3 /opt/oracle-ai-stack/scripts/gstack_full.py',timeout=3600)
        print(p.stdout.decode())
    elif a.action=='update':
        # Do not replace a coherent running stack with mutable branch tips automatically.
        verify_all(a.stage)
        lifecycle(cfg,'backup')
        print('BACKUP_COMPLETE; follow references/lifecycle.md to apply the reviewed version change component-by-component. No running package or database was changed.')
        sys.exit(3)
    else: lifecycle(cfg,a.action,a.snapshot,a.confirm)

if __name__=='__main__':
    try: main()
    except (StackError,ValueError,KeyError,FileNotFoundError) as e:
        print('BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
