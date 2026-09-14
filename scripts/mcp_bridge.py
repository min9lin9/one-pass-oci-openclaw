#!/usr/bin/env python3
"""Restricted command surface; actual MCP tool permissions still need review."""
import json, os, pathlib, subprocess, sys

def main():
    a=sys.argv[1:]
    if not a or a[0] not in ('list','call'): raise ValueError('Only list/call is exposed')
    if any(x.startswith('--') and x not in ('--schema','--json') for x in a):
        raise ValueError('Ad-hoc transport/config/credential options are not allowed')
    if any('://' in x for x in a[:2]): raise ValueError('Only registered server names accepted')
    home=pathlib.Path.home(); isolated=home/'.local/share/oracle-ai-stack/mcp-home'
    cfg=isolated/'config/mcporter.json'
    servers=json.loads(cfg.read_text()).get('mcpServers',{})
    if len(a)>1 and not a[1].startswith('--'):
        server=a[1].split('.',1)[0]
        if server not in servers: raise ValueError('Server is not explicitly configured')
    elif a[0]=='call': raise ValueError('Specify a registered server.tool')
    paths=json.loads((home/'.local/state/oracle-ai-stack/runtime-paths.json').read_text())
    env={'HOME':str(isolated),'XDG_CONFIG_HOME':str(isolated/'.config'),
         'PATH':str(pathlib.Path(paths['node']).parent)+':/usr/bin:/bin','LANG':'C.UTF-8'}
    # No source-client imports: dedicated HOME, explicit config, imports: [] set by installer.
    subprocess.run([paths['mcporter'],'--config',str(cfg),*a],cwd=isolated,env=env,check=True,timeout=120)
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('MCP_BRIDGE_BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
