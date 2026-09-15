#!/usr/bin/env python3
"""Root-side infrastructure worker. Receives secrets over SSH stdin, never argv.
Only execute a reviewed package as the server operator. OpenClaw never receives
operator SSH/Cloudflare/Tailscale/backup credentials.
"""
from __future__ import annotations
import argparse, grp, hashlib, json, os, pathlib, pwd, re, secrets, shutil, subprocess, sys, time
from stacklib import StackError, access_mode, atom_json, domain_name, public_ipv4, require, run, tailnet_ipv4, digest_tree
BASE=pathlib.Path('/opt/oracle-ai-stack')
STATE=pathlib.Path('/var/lib/oracle-ai-stack')
ETC=pathlib.Path('/etc/oracle-ai-stack')
PUBLIC_FIREWALL=pathlib.Path('/etc/systemd/system/oracle-public-https.service')
HOME=pathlib.Path('/home/openclaw')
PREFIX=HOME/'.local/lib/openclaw-cli'
BIN=PREFIX/'bin/openclaw'
BUZZ=BASE/'buzz'
ENVFILE=ETC/'buzz.env'
COMPOSE=BASE/'compose.buzz.private.json'
from profile_spec import PROFILES
OP=PROFILES['operations']
UNIT=OP.unit


def write(path, text, mode=0o600, user=None):
    from fssecure import write_text, FileSafetyError
    u=pwd.getpwnam(user) if user else None
    try: write_text(path,text,mode=mode,uid=u.pw_uid if u else None,gid=u.pw_gid if u else None)
    except FileSafetyError as exc: raise StackError(str(exc)) from exc


def chown_tree(path,user):
    from fssecure import chown_tree as secure_chown, FileSafetyError
    u=pwd.getpwnam(user)
    try: secure_chown(path,u.pw_uid,u.pw_gid)
    except FileSafetyError as exc: raise StackError(str(exc)) from exc


def user_run(user,args,*,env=None,cwd=None,timeout=1200,check=True):
    home=pwd.getpwnam(user).pw_dir
    path=str(PREFIX/'tools/node/bin')+':'+str(PREFIX/'bin')
    if user=='openclaw': path+=':'+str(pathlib.Path(home)/'.local/share/oracle-ai-stack/bun/bin')
    path+=':/usr/local/bin:/usr/bin:/bin'
    cmd=['runuser','-u',user,'--','env','-i','HOME='+home,'USER='+user,'LANG=C.UTF-8','PATH='+path]
    cmd += [k+'='+v for k,v in (env or {}).items()]
    return run(cmd+list(map(str,args)),cwd=cwd,timeout=timeout,check=check)


def oc(*args,check=True):
    from profiles_runtime import oc as profile_oc
    return profile_oc(OP,*args,check=check)

def docker_compose(*args,check=True):
    return run(['docker','compose','-p','oracle-buzz','--project-directory',str(BUZZ/'deploy/compose'),
      '--env-file',str(ENVFILE),'-f',str(COMPOSE),*args],check=check,timeout=2400)


def preflight():
    import platform
    osinfo=dict(line.strip().split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if platform.machine()!='aarch64' or osinfo.get('ID','').strip('"')!='ubuntu' or osinfo.get('VERSION_ID','').strip('"')!='24.04':
        raise StackError('Expected Ubuntu 24.04 aarch64; no mutation performed')
    mem=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemTotal:')))
    if mem<10*1024*1024: raise StackError('Less than expected RAM')
    if shutil.disk_usage('/').free<8*1024**3: raise StackError('Insufficient free space for a fresh build; at least 8 GiB required')
    return {'os':'Ubuntu 24.04','arch':'aarch64','memory_kib':mem}


def user_exists(name):
    try: return pwd.getpwnam(name)
    except KeyError: return None


def select_access_mode(cfg, previous, *, allow_implicit_public=False):
    explicit=bool(cfg.get('_ACCESS_MODE_EXPLICIT', 'ACCESS_MODE' in cfg))
    if explicit:
        return access_mode(cfg)
    if previous.get('access_mode') in ('public','tailscale'):
        return previous['access_mode']
    if previous.get('tailscale_ip'):
        return 'tailscale'
    if allow_implicit_public:
        return access_mode(cfg)
    raise StackError('Existing deployment has no network mode; set ACCESS_MODE explicitly before migration')


def configure_network(cfg,stage,*,allow_implicit_public=False):
    require(cfg,'DOMAIN','CLOUDFLARE_API_TOKEN')
    domain=domain_name(cfg['DOMAIN'])
    network_path=STATE/'network.json'
    previous=json.loads(network_path.read_text()) if network_path.exists() else {}
    managed_path=STATE/'managed.json'
    managed=json.loads(managed_path.read_text()) if managed_path.exists() else {}
    if not network_path.exists() and managed.get('state')=='BOOTSTRAPPING':
        previous={'access_mode':managed.get('access_mode')}
    mode=select_access_mode(cfg,previous,allow_implicit_public=allow_implicit_public)
    conn=cfg.get('_SSH_CONNECTION','').split()
    if len(conn)!=4: raise StackError('No SSH connection metadata; refusing a possibly locking firewall change')
    import ipaddress
    peer=str(ipaddress.ip_address(conn[0])); port=conn[3]
    if not port.isdigit() or not 1 <= int(port) <= 65535: raise StackError('Invalid SSH connection port')
    token=cfg.get('CLOUDFLARE_DNS01_TOKEN') or cfg['CLOUDFLARE_API_TOKEN']
    if any(x in token for x in '\r\n'): raise StackError('Invalid certificate token')
    public_ip=public_ipv4(cfg.get('PUBLIC_IP','')) if mode=='public' else None
    run(['ufw','allow','from',peer,'to','any','port',port,'proto','tcp'])
    if mode=='public':
        ip=public_ip
        run(['ufw','allow','443/tcp'])
        bind='0.0.0.0'
    else:
        if PUBLIC_FIREWALL.exists():
            run(['systemctl','disable','--now',PUBLIC_FIREWALL.name])
        if previous.get('access_mode')=='public':
            run(['ufw','--force','delete','allow','443/tcp'])
        run(['ufw','allow','in','on','tailscale0','to','any','port','443','proto','tcp'])
        run(['ufw','allow','in','on','tailscale0','to','any','port',port,'proto','tcp'])
        if not shutil.which('tailscale'):
            run(['bash',str(stage/'core/tailscale-install.sh')],timeout=900)
        run(['systemctl','enable','--now','tailscaled'])
        ts=run(['tailscale','status','--json'],check=False)
        try: online=json.loads(ts.stdout).get('BackendState')=='Running'
        except ValueError: online=False
        if not online:
            require(cfg,'TAILSCALE_AUTH_KEY')
            key=ETC/'tailscale-auth.once'; write(key,cfg['TAILSCALE_AUTH_KEY'])
            try: run(['tailscale','up','--auth-key=file:'+str(key),'--ssh=false','--accept-dns=false'],timeout=180)
            finally: key.unlink(missing_ok=True)
        ip=tailnet_ipv4(run(['tailscale','ip','-4']).stdout.decode().strip().splitlines()[0])
        bind=ip
    run(['ufw','default','deny','incoming'])
    run(['ufw','--force','enable'])
    if mode=='public':
        # OCI images can have a terminal INPUT reject before every UFW chain.
        # Own only this tagged 443 exception; do not flush or reorder other rules.
        rule='-p tcp --dport 443 -m comment --comment oracle-ai-stack-https -j ACCEPT'
        unit=('[Unit]\nDescription=OpenClaw public HTTPS ingress\n'
              'After=netfilter-persistent.service ufw.service\n'
              '[Service]\nType=oneshot\nRemainAfterExit=true\n'
              'ExecStart=/usr/sbin/iptables -I INPUT 1 '+rule+'\n'
              'ExecStop=/usr/sbin/iptables -D INPUT '+rule+'\n'
              '[Install]\nWantedBy=multi-user.target\n')
        write(PUBLIC_FIREWALL,unit,0o644)
        run(['systemctl','daemon-reload'])
        run(['systemctl','enable',PUBLIC_FIREWALL.name])
        run(['systemctl','restart',PUBLIC_FIREWALL.name])
    write(ETC/'proxy.env',f'DOMAIN={domain}\nPROXY_BIND={bind}\nCLOUDFLARE_API_TOKEN={token}\n')
    network={'domain':domain,'access_mode':mode,'dns_ip':ip,'ssh_peer':peer,'ssh_port':port}
    network['public_ip' if mode=='public' else 'tailscale_ip']=ip
    atom_json(network_path,network)
    if managed.get('state')=='BOOTSTRAPPING':
        managed['state']='HOST_CONFIGURED'
        atom_json(managed_path,managed)
    return {'phase':'NETWORK_CONFIGURED','access_mode':mode,'dns_ip':ip,
            'public_ip' if mode=='public' else 'tailscale_ip':ip}


def init_host(cfg,stage):
    preflight(); require(cfg,'DOMAIN','CLOUDFLARE_API_TOKEN')
    domain=domain_name(cfg['DOMAIN'])
    new_install=not (STATE/'managed.json').exists()
    if new_install:
        if user_exists('openclaw'):
            raise StackError('An unmanaged/old deployment exists; use the migration runbook, not zero-base overwrite')
        for d in (BASE,STATE,ETC): d.mkdir(parents=True,exist_ok=True)
        STATE.chmod(0o700); ETC.chmod(0o700)
        atom_json(STATE/'managed.json',{'schema':3,'domain':domain,'state':'BOOTSTRAPPING',
                                     'access_mode':access_mode(cfg)})
    elif json.loads((STATE/'managed.json').read_text())['domain']!=domain:
        raise StackError('Deployment domain mismatch; explicit migration required')
    if json.loads((STATE/'managed.json').read_text()).get('schema')!=3:
        raise StackError('v0.2 single-profile deployment requires explicit migration; no automatic state/auth reassignment')
    env=dict(os.environ,DEBIAN_FRONTEND='noninteractive')
    run(['apt-get','update'],env=env,timeout=900)
    run(['apt-get','install','-y','ca-certificates','curl','git','jq','openssl','ufw','sudo','unzip',
         'python3','python3-venv','python3-cryptography','docker.io','docker-compose-v2','restic','gitleaks',
         'iptables','build-essential','libnss3','libatk1.0-0','libatk-bridge2.0-0','libcups2t64',
         'libdrm2','libxkbcommon0','libxcomposite1','libxdamage1','libxfixes3','libxrandr2',
         'libgbm1','libpango-1.0-0','libcairo2','libasound2t64'],env=env,timeout=1800)
    version=run(['docker','compose','version','--short']).stdout.decode().strip().lstrip('v')
    nums=tuple(int(x) for x in re.findall(r'\d+',version)[:3])
    if nums<(2,24,4): raise StackError('Docker Compose >=2.24.4 required')
    run(['systemctl','enable','--now','docker'])
    for name in ('openclaw','clawfetch'):
        if not user_exists(name): run(['useradd','--create-home','--shell','/bin/bash',name])
        u=pwd.getpwnam(name); pathlib.Path(u.pw_dir).chmod(0o700)
        groups={g.gr_name for g in grp.getgrall() if name in g.gr_mem or g.gr_gid==u.pw_gid}
        if groups & {'sudo','docker','root'}: raise StackError('Agent accounts may not be in sudo/docker/root groups')
    result=configure_network(cfg,stage,allow_implicit_public=new_install)
    result['phase']='HOST_CONFIGURED'
    return result


def keypair():
    from cryptography.hazmat.primitives.asymmetric import ec
    key=ec.generate_private_key(ec.SECP256K1())
    return {'private':key.private_numbers().private_value.to_bytes(32,'big').hex(),
            'public':key.public_key().public_numbers().x.to_bytes(32,'big').hex()}


def ensure_keys(cfg):
    path=STATE/'identities.json'
    if path.exists(): return json.loads(path.read_text())
    keys={k:keypair() for k in ('owner','relay','bot')}
    if cfg.get('BUZZ_OWNER_PUBKEY'):
        if not re.fullmatch('[0-9a-f]{64}',cfg['BUZZ_OWNER_PUBKEY']): raise StackError('Owner pubkey must be 64 lowercase hex')
        keys['owner']={'public':cfg['BUZZ_OWNER_PUBKEY']}
    atom_json(path,keys)
    return keys


def buzz_install(cfg,stage,lock):
    if not BUZZ.exists(): shutil.copytree(stage/'core/buzz',BUZZ)
    elif digest_tree(BUZZ) != lock['buzz_tree_sha256']:
        raise StackError('Buzz checkout differs from reviewed lock; update uses a new versioned deployment')
    keys=ensure_keys(cfg); domain=domain_name(cfg['DOMAIN'])
    image='ghcr.io/block/buzz:sha-'+lock['buzz_commit'][:7]
    if not ENVFILE.exists():
        values={'BUZZ_IMAGE':image,'BUZZ_DOMAIN':'buzz.'+domain,'RELAY_URL':'wss://buzz.'+domain,
          'BUZZ_MEDIA_BASE_URL':'https://buzz.'+domain+'/media','BUZZ_MEDIA_SERVER_DOMAIN':'buzz.'+domain,
          'BUZZ_CORS_ORIGINS':'https://buzz.'+domain,'RELAY_OWNER_PUBKEY':keys['owner']['public'],
          'BUZZ_RELAY_PRIVATE_KEY':keys['relay']['private'],'BUZZ_GIT_HOOK_HMAC_SECRET':secrets.token_hex(32),
          'POSTGRES_DB':'buzz','POSTGRES_USER':'buzz','POSTGRES_PASSWORD':secrets.token_hex(24),
          'REDIS_PASSWORD':secrets.token_hex(24),'BUZZ_S3_ACCESS_KEY':secrets.token_hex(16),
          'BUZZ_S3_SECRET_KEY':secrets.token_hex(32),'BUZZ_S3_BUCKET':'buzz-media',
          'BUZZ_REQUIRE_AUTH_TOKEN':'true','BUZZ_REQUIRE_RELAY_MEMBERSHIP':'true',
          'BUZZ_ALLOW_NIP_OA_AUTH':'true','BUZZ_AUTO_MIGRATE':'true','BUZZ_HTTP_PORT':'3000'}
        write(ENVFILE,'\n'.join(k+'='+v for k,v in values.items())+'\n')
    # Resolve official compose, sanitize actual JSON BEFORE creating any container.
    renderdir=BASE/'buzz-render'
    renderdir.mkdir(exist_ok=True); renderdir.chmod(0o700)
    shutil.copyfile(BUZZ/'deploy/compose/compose.yml',renderdir/'compose.yml')
    shutil.copyfile(ENVFILE,renderdir/'.env'); (renderdir/'.env').chmod(0o600)
    raw=run(['docker','compose','--project-directory',str(renderdir),'--env-file',str(ENVFILE),
             '-f',str(renderdir/'compose.yml'),'config','--format','json']).stdout
    compose=json.loads(raw)
    if set(compose.get('services',{})) != {'relay','postgres','redis','minio','minio-init'}:
        raise StackError('Buzz compose services changed; re-review topology')
    for name,s in compose['services'].items():
        s.pop('ports',None)
        if s.get('privileged') or s.get('network_mode')=='host': raise StackError('Unexpected privileged Buzz service')
        for v in s.get('volumes',[]):
            if isinstance(v,dict) and v.get('type')=='bind': raise StackError('Unexpected upstream bind mount')
        s['restart']='unless-stopped' if name!='minio-init' else 'no'
        s.setdefault('logging',{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}})
    compose['services']['relay']['ports']=[{'target':3000,'published':'3000','host_ip':'127.0.0.1','protocol':'tcp'}]
    # Remove upstream project-specific volume/network names; use our fixed project.
    compose['name']='oracle-buzz'
    for n,v in compose.get('volumes',{}).items(): v['name']='oracle-buzz_'+n
    for n,v in compose.get('networks',{}).items(): v['name']='oracle-buzz_'+n
    # Initial resolution is explicit; subsequent restarts reuse recorded digests.
    digestpath=STATE/'buzz-image-digests.json'
    pinned=json.loads(digestpath.read_text()) if digestpath.exists() else {}
    for name,s in compose['services'].items():
        ref=s['image']
        if name in pinned:
            s['image']=pinned[name]; continue
        run(['docker','pull','--platform','linux/arm64',ref],timeout=1800)
        inspected=json.loads(run(['docker','image','inspect',ref]).stdout)[0]
        if inspected.get('Architecture')!='arm64': raise StackError('Image is not ARM64: '+name)
        if name=='relay':
            revision=inspected.get('Config',{}).get('Labels',{}).get('org.opencontainers.image.revision')
            if revision and revision!=lock['buzz_commit']: raise StackError('Buzz image/source commit mismatch')
        ds=inspected.get('RepoDigests',[])
        if not ds: raise StackError('Image digest unavailable: '+name)
        s['image']=ds[0]; pinned[name]=ds[0]
    atom_json(digestpath,pinned)
    # Expanded compose contains secrets. Root-only path, never printed or sent to agent.
    atom_json(COMPOSE,compose)
    docker_compose('up','-d','--wait','--wait-timeout','240')
    membership=STATE/'bot-relay-membership.json'
    if not membership.exists():
        docker_compose('exec','-T','relay','/usr/local/bin/buzz-admin','add-member',
                       '--pubkey',keys['bot']['public'],'--role','member')
        atom_json(membership,{'public_key':keys['bot']['public'],'state':'ADDED_NOT_ROOM_APPROVED'})
    return {'phase':'BUZZ_RELAY_INSTALLED','bot_public_key':keys['bot']['public'],
            'owner_public_key':keys['owner']['public'],'room_status':'BOT_ROLE_STILL_REQUIRED'}


def openclaw_install(cfg,stage,lock):
    from profiles_runtime import install
    return install(cfg,stage,lock)


def proxy_install(cfg,lock):
    net=json.loads((STATE/'network.json').read_text())
    # Reuse both parent digests and the built image on repair; no floating rebuild.
    buildlock=STATE/'caddy-build-lock.json'
    if buildlock.exists():
        locked=json.loads(buildlock.read_text())
        if locked['cloudflare_commit']!=lock['caddy_dns_commit']:
            raise StackError('Caddy module changed; use the reviewed upgrade procedure')
        digests=locked['parents']; caddy_version=locked['caddy_version']
    else:
        digests={}
        for tag in ('caddy:2-builder','caddy:2-alpine'):
            run(['docker','pull','--platform','linux/arm64',tag],timeout=1200)
            o=json.loads(run(['docker','image','inspect',tag]).stdout)[0]
            if o['Architecture']!='arm64': raise StackError('Caddy image not ARM64')
            digests[tag]=o['RepoDigests'][0]
        raw=run(['docker','run','--rm','--entrypoint','caddy',digests['caddy:2-alpine'],'version']).stdout.decode()
        caddy_version=raw.split()[0]
        if not re.fullmatch(r'v2\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',caddy_version):
            raise StackError('Could not pin Caddy core version')
        locked={'parents':digests,'cloudflare_commit':lock['caddy_dns_commit'],'caddy_version':caddy_version}
        atom_json(buildlock,locked)
    builddir=BASE/'caddy-build'; builddir.mkdir(exist_ok=True)
    # The build context must not contain generated Compose credentials or source caches.
    write(builddir/'.dockerignore','**\n!Dockerfile\n',0o644)
    write(builddir/'Dockerfile',f'FROM {digests["caddy:2-builder"]} AS builder\n'
          f'RUN xcaddy build {caddy_version} --with github.com/caddy-dns/cloudflare@{lock["caddy_dns_commit"]}\n'
          f'FROM {digests["caddy:2-alpine"]}\nCOPY --from=builder /usr/bin/caddy /usr/bin/caddy\n',0o644)
    image='oracle-ai-caddy:'+hashlib.sha256(json.dumps(locked,sort_keys=True).encode()).hexdigest()[:20]
    if run(['docker','image','inspect',image],check=False).returncode:
        run(['docker','build','--platform','linux/arm64','--tag',image,str(builddir)],timeout=2400)
    mode=net.get('access_mode') or ('tailscale' if net.get('tailscale_ip') else None)
    if mode not in ('public','tailscale'):
        raise StackError('Network mode is missing; run the explicit network configuration action')
    write(BASE/'Caddyfile','''{\n    admin off\n    auto_https disable_redirects\n}\nhttps://openclaw.{$DOMAIN} {\n    bind {$PROXY_BIND}\n    tls {\n        dns cloudflare {$CLOUDFLARE_API_TOKEN}\n    }\n    reverse_proxy 127.0.0.1:18789\n}\n''',0o644)
    proxy={'name':'oracle-proxy','services':{'proxy':{'image':image,
           'network_mode':'host','env_file':[str(ETC/'proxy.env')],
           'volumes':[str(BASE/'Caddyfile')+':/etc/caddy/Caddyfile:ro','oracle-proxy-data:/data','oracle-proxy-config:/config'],
           'restart':'unless-stopped','logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}}},
           'volumes':{'oracle-proxy-data':{'name':'oracle-proxy-data'},'oracle-proxy-config':{'name':'oracle-proxy-config'}}}
    atom_json(BASE/'compose.proxy.json',proxy)
    run(['docker','compose','-f',str(BASE/'compose.proxy.json'),'up','-d','--no-build','--force-recreate'],timeout=2400)
    return {'phase':'PUBLIC_PROXY_INSTALLED' if mode=='public' else 'TAILSCALE_PROXY_INSTALLED',
            'access_mode':mode,'dns_ip':net.get('dns_ip') or net.get('public_ip') or net.get('tailscale_ip')}


def extensions_install(stage):
    # Source snapshots are public and reviewed; agent can read them, not operator secrets.
    for p in [stage,*stage.rglob('*')]:
        if not p.is_symlink(): p.chmod(0o755 if p.is_dir() or p.stat().st_mode&0o111 else 0o644)
    user_run('openclaw',['/usr/bin/python3',str(BASE/'scripts/extensions.py'),'apply','--stage',str(stage),'--home',str(HOME)],timeout=1800)
    user_run('openclaw',['/usr/bin/python3',str(BASE/'scripts/runtime_setup.py')],timeout=3600)
    # Give only the public search source to a separate UID; not the agent's auth state.
    fetchsource=stage/'sources/insane-search'
    user_run('clawfetch',['/usr/bin/python3',str(BASE/'scripts/fetch_runtime_setup.py'),str(fetchsource)],timeout=2400)
    unit='''[Unit]\nDescription=Private-address egress deny for public-page reader\nAfter=network-online.target ufw.service docker.service\n[Service]\nType=oneshot\nExecStart=/bin/bash /opt/oracle-ai-stack/scripts/fetch_egress.sh\nRemainAfterExit=true\n[Install]\nWantedBy=multi-user.target\n'''
    write('/etc/systemd/system/oracle-fetch-egress.service',unit,0o644)
    run(['systemctl','daemon-reload']); run(['systemctl','enable','--now','oracle-fetch-egress.service'])
    sudoers='openclaw ALL=(clawfetch) NOPASSWD: /usr/bin/python3 /opt/oracle-ai-stack/scripts/public_read.py *\n'
    candidate=ETC/'fetch.sudoers'; write(candidate,sudoers,0o440)
    run(['visudo','-cf',str(candidate)])
    write('/etc/sudoers.d/oracle-public-reader',sudoers,0o440)
    # These adapters belong only to the operations profile, never worker profiles.
    user_run('openclaw',['/usr/bin/python3',str(BASE/'scripts/ops_adapters.py')],timeout=180)
    oc('skills','check')
    run(['systemctl','restart',UNIT])
    return {'phase':'EXTENSIONS_INSTALLED','runtime_smokes':'PASS','live_tasks':'NOT_YET_TESTED'}


def bind_buzz(cfg):
    require(cfg,'BUZZ_ROOM_ID')
    ready=STATE/'model-operations.json'
    if not ready.exists() or json.loads(ready.read_text()).get('auth_probe')!='PASS':
        raise StackError('Authenticate operations and run models before binding its user-facing Buzz channel')
    import uuid
    room=str(uuid.UUID(cfg['BUZZ_ROOM_ID']))
    keys=json.loads((STATE/'identities.json').read_text())
    path=OP.state/'openclaw.json'; config=json.loads(path.read_text())
    config.setdefault('channels',{})['buzz']={'enabled':True,'name':'OpenClaw',
       'relayUrl':'wss://buzz.'+json.loads((STATE/'network.json').read_text())['domain'],
       'privateKey':keys['bot']['private'],'groupPolicy':'allowlist',
       'groupAllowFrom':[keys['owner']['public']], 'groups':{room:{'requireMention':False}},'defaultTo':room}
    old=path.read_bytes(); atom_json(path,config); chown_tree(OP.state,'openclaw')
    try: oc('config','validate')
    except Exception: write(path,old.decode(),user='openclaw'); raise
    run(['systemctl','restart',UNIT])
    probe=oc('channels','status','--channel','buzz','--probe',check=False)
    return {'phase':'BUZZ_CONFIGURED','probe_exit':probe.returncode,
      'note':'Room-owner Bot-role approval is required; relay membership alone is insufficient'}


def status(probe=False):
    network_path=STATE/'network.json'
    net=json.loads(network_path.read_text()) if network_path.exists() else {}
    mode=net.get('access_mode') or ('tailscale' if net.get('tailscale_ip') else 'UNKNOWN')
    checks={'network':'PASS' if mode in ('public','tailscale') else 'MISSING'}
    commands=[('openclaw',['systemctl','is-active',UNIT]),
              ('docker',['systemctl','is-active','docker']),
              ('fetch_egress',['systemctl','is-active','oracle-fetch-egress.service'])]
    if mode=='public': commands.append(('network_firewall',['systemctl','is-active',PUBLIC_FIREWALL.name]))
    if mode=='tailscale': commands.insert(0,('tailscale',['systemctl','is-active','tailscaled']))
    for label,cmd in commands:
        checks[label]='PASS' if run(cmd,check=False).returncode==0 else 'FAIL'
    proxy_file=BASE/'compose.proxy.json'
    if proxy_file.exists():
        result=run(['docker','compose','-f',str(proxy_file),'ps','--status','running','--services'],check=False)
        checks['proxy']='PASS' if result.returncode==0 and set(result.stdout.decode().split())=={'proxy'} else 'FAIL'
    else:
        checks['proxy']='MISSING'
    checks['oauth']='NOT_PROBED'
    r=HOME/'.local/state/oracle-ai-stack/runtime-checks.json'
    checks['extension_smokes']='RECORDED_NOT_REVALIDATED' if r.exists() else 'MISSING'
    from profiles_runtime import profile_status
    checks['profiles']=profile_status(probe=probe)
    checks['gbrain']='INSTALLED_NOT_CHAT_VERIFIED' if (STATE/'gbrain-install.json').exists() else 'MISSING'
    from evidence import delegation_receipt
    checks['worker_roundtrip']=delegation_receipt(STATE/'acceptance.json')
    if probe:
        checks['oauth']=checks['profiles'].get('operations',{}).get('auth','NOT_PROBED')
    required=['network','openclaw','docker','fetch_egress','proxy']
    if mode=='public': required.append('network_firewall')
    if mode=='tailscale': required.append('tailscale')
    services_ready=all(checks[name]=='PASS' for name in required)
    profiles_ready=len(checks['profiles'])==len(PROFILES) and all(
        row.get('gateway')=='PASS' for row in checks['profiles'].values())
    installs_ready=checks['extension_smokes']!='MISSING' and checks['gbrain']!='MISSING'
    auth_ready=not probe or all(row.get('auth')=='PASS' for row in checks['profiles'].values())
    return {'checks':checks,'access_mode':mode,
            'overall':'SERVICES_RUNNING' if services_ready and profiles_ready and installs_ready and auth_ready else 'INCOMPLETE',
            'client_verification':'NOT_TESTED'}


def main():
    if os.geteuid()!=0: raise StackError('Server operator/root context required')
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['preflight','host','network','openclaw','proxy','extensions','status','models','profiles','gbrain','memory-smoke','acceptance'])
    p.add_argument('--stage',type=pathlib.Path,default=BASE/'stage')
    p.add_argument('--probe',action='store_true'); a=p.parse_args()
    cfg=json.load(sys.stdin) if not sys.stdin.isatty() else {}
    cfg['_SSH_CONNECTION']=os.environ.get('SSH_CONNECTION',cfg.get('_SSH_CONNECTION',''))
    lock=json.loads((a.stage/'deployment.lock.json').read_text()) if (a.stage/'deployment.lock.json').exists() else {}
    if a.action=='preflight': result=preflight()
    elif a.action=='host': result=init_host(cfg,a.stage)
    elif a.action=='network': result=configure_network(cfg,a.stage)
    elif a.action=='openclaw': result=openclaw_install(cfg,a.stage,lock)
    elif a.action=='proxy': result=proxy_install(cfg,lock)
    elif a.action=='extensions': result=extensions_install(a.stage)
    elif a.action=='models':
        from profiles_runtime import configure_models
        result=configure_models(cfg,cfg.get('profile'))
    elif a.action=='profiles':
        from profiles_runtime import profile_status
        result=profile_status(probe=a.probe)
    elif a.action in ('gbrain','memory-smoke'):
        from gbrain_install import install,smoke
        was_active=run(['systemctl','is-active','--quiet',UNIT],check=False).returncode==0
        run(['systemctl','stop',UNIT])
        try:result=install(a.stage,lock) if a.action=='gbrain' else smoke()
        finally:
            if was_active:run(['systemctl','start',UNIT])
    elif a.action=='acceptance':
        from acceptance import smoke
        result=smoke()
    else: result=status(a.probe)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try:
        from operator_lock import locked
        with locked(): main()
    except Exception as e:
        print(json.dumps({'error':type(e).__name__,'message':str(e)}),file=sys.stderr); sys.exit(2)
