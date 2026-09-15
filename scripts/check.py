#!/usr/bin/env python3
"""Offline checks only: never provision infrastructure or authenticate a model."""
import ast,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    for p in ROOT.rglob('*.py'):
        if '.git' in p.parts:continue
        ast.parse(p.read_text(),filename=str(p))
    for p in ROOT.rglob('*.json'):
        if '.git' in p.parts:continue
        json.loads(p.read_text())
    for p in (ROOT/'scripts').glob('*.sh'):subprocess.run(['bash','-n',str(p)],check=True)
    env=dict(os.environ,TMPDIR=str(pathlib.Path(tempfile.gettempdir()).resolve()))
    p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,env=env)
    if p.returncode:return p.returncode
    print('OFFLINE_CHECKS_PASSED; OCI/ARM/auth/OpenClaw HTTPS/GBrain/gstack end-to-end remain untested')
    return 0
if __name__=='__main__':raise SystemExit(main())
