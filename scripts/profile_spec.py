"""Authoritative profile layout. Names are real OpenClaw CLI profiles, not personas.
The Unix accounts, config/state, gateway ports, model env, and workspaces differ.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from stacklib import StackError

@dataclass(frozen=True)
class Profile:
    name: str
    user: str
    port: int
    agent: str
    @property
    def home(self): return Path('/home') / self.user
    @property
    def state(self): return self.home / ('.openclaw-' + self.name)
    @property
    def workspace(self): return self.state / 'workspace'
    @property
    def prefix(self): return self.home / '.local/lib/openclaw-cli'
    @property
    def binary(self): return self.prefix / 'bin/openclaw'
    @property
    def unit(self): return 'oracle-openclaw-' + self.name + '.service'
    @property
    def env_file(self): return Path('/etc/oracle-ai-stack') / ('model-' + self.name + '.env')

PROFILES = {
    'operations': Profile('operations', 'openclaw', 18789, 'operations'),
    'planning': Profile('planning', 'clawplan', 19789, 'planner'),
    'development': Profile('development', 'clawdev', 20789, 'developer'),
    'finance': Profile('finance', 'clawfin', 21789, 'finance'),
}

# User-facing profiles get an interactive agent with messaging; workers do not.
USER_FACING = frozenset({'operations', 'finance'})
WORKERS = frozenset({'planning', 'development'})

def get_profile(name: str) -> Profile:
    if name not in PROFILES: raise StackError('Unknown profile; use operations, planning, development, or finance')
    return PROFILES[name]

def auth_mode(cfg: dict, name: str) -> str:
    catalog = cfg.get('OPENCODE_CATALOG') or 'go'
    if catalog not in ('zen', 'go'): raise StackError('OPENCODE_CATALOG must be zen or go')
    default = 'chatgpt' if name in USER_FACING or not cfg.get('OPENCODE_API_KEY') else ('opencode-go' if catalog == 'go' else 'opencode')
    mode = cfg.get(name.upper() + '_AUTH') or default
    if mode not in ('chatgpt', 'opencode', 'opencode-go'): raise StackError('Unsupported profile authentication mode')
    return mode

def provider_for(mode: str) -> str: return 'openai' if mode == 'chatgpt' else mode

def validate_model(model: str, provider: str) -> str:
    if not isinstance(model, str) or not re.fullmatch(r'[a-z0-9-]+/[A-Za-z0-9._:-]+', model) or model.split('/')[0] != provider:
        raise StackError('Model must be an explicit ref in the selected provider catalog')
    return model

def choose_model(rows: list, provider: str, requested: str = '') -> str:
    choices=[]
    for row in rows:
        key = row.get('key') or row.get('id') or row.get('model')
        if not isinstance(key, str) or not key.startswith(provider + '/'): continue
        if row.get('available') is False or row.get('missingAuth') is True or row.get('deprecated') is True: continue
        choices.append(validate_model(key, provider))
    if requested:
        requested=validate_model(requested, provider)
        if requested not in choices: raise StackError('Requested model absent from active catalog; no silent model substitution')
        return requested
    if not choices: raise StackError('No active model in catalog; authenticate and check entitlement')
    # Use a documented preference only when actually returned by this installation.
    preferred = {'openai':'gpt-6-astra', 'opencode':'gpt-5.6-sol', 'opencode-go':'kimi-k3'}
    wanted=provider+'/'+preferred[provider]
    return wanted if wanted in choices else sorted(set(choices))[0]

def config_for(p: Profile, cfg: dict, token: str) -> dict:
    mode=auth_mode(cfg,p.name); provider=provider_for(mode)
    requested=cfg.get(p.name.upper()+'_MODEL','')
    model=validate_model(requested,provider) if requested else None
    allowed = ['read','web_search','web_fetch'] if p.name=='planning' else ['read','write','edit','apply_patch','exec','process','web_search','web_fetch']
    if p.name in USER_FACING: allowed += ['message','memory_search','memory_get']
    denied = ['exec','process','write','edit','apply_patch','message','gateway','cron','nodes','sessions_spawn','sessions_send'] if p.name=='planning' else ['gateway','cron','nodes','sessions_spawn','sessions_send']
    if p.name=='development': denied += ['message']
    result={
      'gateway': {'mode':'local','bind':'loopback','port':p.port,'auth':{'mode':'token','token':token}},
      'agents': {'defaults': {'workspace':str(p.workspace),'model':{'primary':model,'fallbacks':[]},'maxConcurrent':1,'timeoutSeconds':600},
                 'entries':{p.agent:{'workspace':str(p.workspace),'agentDir':str(p.state/'agents'/p.agent/'agent')}}},
      'tools': {'allow':allowed,'deny':denied,'elevated':{'enabled':False},'fs':{'workspaceOnly':True}},
      # Keep tool policies in OpenClaw's embedded runtime, including ChatGPT OAuth.
      # Do not implicitly switch the planner into a coding harness with its own tools.
      'models': {'providers': {'openai': {'agentRuntime': {'id':'openclaw'}}}},
    }
    if model is None:
        result['agents']['defaults'].pop('model')  # Auth/catalog discovery precedes any accepted worker task.
    if p.name=='operations':
        url='https://openclaw.'+cfg['DOMAIN']
        result['gateway'].update({'publicOrigin':url,'trustedProxies':['127.0.0.1','::1'],'controlUi':{'allowedOrigins':[url]}})
    return result

def environment(p: Profile) -> dict[str,str]:
    return {'HOME':str(p.home),'USER':p.user,'LANG':'C.UTF-8',
        'PATH':str(p.prefix/'tools/node/bin')+':'+str(p.prefix/'bin')+
            (':'+str(p.home/'.local/share/oracle-ai-stack/bun/bin') if p.name=='operations' else '')+
            ':/usr/local/bin:/usr/bin:/bin',
        'OPENCLAW_STATE_DIR':str(p.state),'OPENCLAW_CONFIG_PATH':str(p.state/'openclaw.json'),
        'CODEX_HOME':str(p.home/'.codex'), 'DO_NOT_TRACK':'1'}

def gateway_unit(p: Profile) -> str:
    env='\n'.join('Environment='+k+'='+v for k,v in environment(p).items())
    # Workers never acquire additional Unix privileges. Ops has only the inherited
    # fixed sudo-to-public-reader rule, not administrative sudo or Docker access.
    nnp='false' if p.name=='operations' else 'true'
    return f'''[Unit]
Description=Oracle OpenClaw {p.name} profile
After=network-online.target
Wants=network-online.target
[Service]
Slice=oracle-agents.slice
User={p.user}
Group={p.user}
WorkingDirectory={p.workspace}
{env}
EnvironmentFile=-{p.env_file}
ExecStart={p.binary} --profile {p.name} gateway run --port {p.port}
Restart=always
RestartSec=5
UMask=0077
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={p.home}
ReadOnlyPaths={p.workspace}/AGENTS.md
NoNewPrivileges={nnp}
MemoryHigh=2G
MemoryMax=3G
TasksMax=256
[Install]
WantedBy=multi-user.target
'''
