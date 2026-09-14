"""Read-only, dependency-free validation before uploading privileged code.
Only fresh hosts or a same-domain v0.3-layout managed installation are accepted.
This is a precondition check, not a complete adversarial filesystem sandbox.
"""
import json, os, pathlib, platform, pwd

def validate(payload, base=pathlib.Path('/opt/oracle-ai-stack'),
             state=pathlib.Path('/var/lib/oracle-ai-stack'), account_lookup=pwd.getpwnam):
    for path in (base,state,pathlib.Path('/etc/oracle-ai-stack')):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise RuntimeError('Refusing linked installation path')
    marker=state/'managed.json'
    if marker.is_symlink(): raise RuntimeError('Refusing linked management marker')
    if marker.exists():
        data=json.loads(marker.read_text())
        if data.get('domain')!=payload['domain'] or data.get('schema')!=3:
            raise RuntimeError('Existing deployment needs explicit migration')
        if marker.stat().st_uid!=0 or state.stat().st_mode & 0o022:
            raise RuntimeError('Management state must be root-owned and not writable by agents')
    else:
        if base.exists() and any(base.iterdir()):
            raise RuntimeError('Unmanaged installation directory already exists')
        for name in ('openclaw','clawplan','clawdev','clawfetch'):
            try: account_lookup(name)
            except KeyError: continue
            raise RuntimeError('Existing agent account requires reviewed adoption')
    if base.exists():
        if base.stat().st_uid!=0 or base.stat().st_mode & 0o022:
            raise RuntimeError('Installation directory must be root-owned and not writable by agents')
        for path in base.rglob('*'):
            if path.is_symlink(): raise RuntimeError('Link found in privileged installation tree')
            if path.stat().st_uid!=0 or path.stat().st_mode & 0o022:
                raise RuntimeError('Untrusted ownership or write access in installer tree')
    return {'state':'TARGET_PRECONDITIONS_PASSED','mutation':False}

def main():
    if os.geteuid()!=0: raise RuntimeError('Read-only root preflight required')
    release=dict(line.strip().split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if platform.machine()!='aarch64' or release.get('ID','').strip('"')!='ubuntu' or release.get('VERSION_ID','').strip('"')!='24.04':
        raise RuntimeError('Expected Ubuntu 24.04 ARM64')
    import sys
    print(json.dumps(validate(json.load(sys.stdin))))
if __name__=='__main__':
    try:main()
    except Exception:
        import sys
        print('TARGET_PREFLIGHT_BLOCKED: unmanaged host, ownership, OS or layout conflict',file=sys.stderr);sys.exit(2)
