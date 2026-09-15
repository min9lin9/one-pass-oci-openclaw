#!/usr/bin/env python3
"""Initial import to the exact user-requested repository. Requires local gh login.
Default visibility: private. --public is an explicit publication decision.
Never overwrite a nonempty repository, force-push, change account permissions,
copy runtime state, or automatically star any repository.
"""
from __future__ import annotations
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile
from package_manifest import MANIFEST, verify, selected, PackageError
from process_guard import run_bounded

REPO='min9lin9/one-pass-oci-openclaw'
ROOT=pathlib.Path(__file__).resolve().parents[1]

class PublishError(RuntimeError):pass

def command(args,*,cwd=None,env=None,check=True):
    result=run_bounded(args,cwd=cwd,env=env,timeout=180)
    if check and result.returncode:raise PublishError('GitHub/Git command failed; inspect local authentication/access without sharing raw credentials')
    return result

def git_env():
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_COUNT='0',GIT_TERMINAL_PROMPT='0',GH_PROMPT_DISABLED='1')
    return env

def git(*args,cwd=None,check=True):
    return command(['git','-c','core.hooksPath=/dev/null','-c','init.templateDir=',
                    '-c','credential.helper=',
                    '-c','credential.https://github.com.helper=!gh auth git-credential',*args],
                    cwd=cwd,env=git_env(),check=check)

def run(root,*,apply=False,public=False):
    manifest=verify(root)
    plan={'repository':REPO,'visibility':'public' if public else 'private',
          'files':len(manifest['files']),'credentials_uploaded':False,
          'mutation':bool(apply),'nonempty_remote':'REFUSE','force_push':False}
    if not apply:return dict(plan,state='PLAN_ONLY_NO_NETWORK')
    if not shutil.which('gh') or not shutil.which('git'):raise PublishError('Install GitHub CLI and Git locally; no credentials are stored in this package')
    who=json.loads(command(['gh','api','user']).stdout)
    if who.get('login','').lower()!='min9lin9':raise PublishError('Authenticate gh as min9lin9; refusing to publish under another account')
    result=command(['gh','api','repos/'+REPO],check=False)
    if result.returncode:
        # Only a JSON 404 response qualifies for an attempted create. Transport or
        # rate-limit failures must not be mistaken for non-existence.
        try:error=json.loads(result.stdout)
        except ValueError:raise PublishError('Repository lookup failed without a confirmed 404; no mutation')
        if str(error.get('status'))!='404':raise PublishError('Repository lookup did not confirm 404; no mutation')
        command(['gh','repo','create',REPO,'--public' if public else '--private',
                 '--description','Reviewed local Codex skill: OCI provisioning, private OpenClaw, isolated profiles'])
    metadata=json.loads(command(['gh','api','repos/'+REPO]).stdout)
    if metadata.get('full_name','').lower()!=REPO.lower():raise PublishError('Unexpected repository identity')
    if not metadata.get('permissions',{}).get('push'):raise PublishError('No push permission for the exact target repository')
    if not metadata.get('private') and not public:raise PublishError('Existing repository is public; rerun with explicit --public approval or choose a private target separately')
    url='https://github.com/'+REPO+'.git'
    refs=git('ls-remote',url).stdout.strip()
    if refs:raise PublishError('Repository is nonempty; no overwrite. Review a normal branch/PR from its current state instead')
    with tempfile.TemporaryDirectory(prefix='one-pass-publish-') as td:
        td=pathlib.Path(td)
        for name,blob,mode in selected(root):
            dest=td/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob);dest.chmod(0o755 if mode else 0o644)
        (td/MANIFEST).write_bytes((pathlib.Path(root)/MANIFEST).read_bytes())
        # Check the copied bytes before creating any Git objects.
        verify(td)
        git('init','-q','-b','main',str(td))
        git('add','--all',cwd=td)
        git('-c','user.name=min9lin9','-c','user.email=min9lin9@users.noreply.github.com',
            '-c','commit.gpgsign=false','commit','-qm','Import reviewed one-pass OCI OpenClaw skill v0.4-beta',cwd=td)
        commit=git('rev-parse','HEAD',cwd=td).stdout.decode().strip()
        # Plain, non-force push fails if another writer created main in the meantime.
        git('push',url,'HEAD:refs/heads/main',cwd=td)
        actual=git('ls-remote',url,'refs/heads/main').stdout.decode().split()
        if not actual or actual[0]!=commit:raise PublishError('Push result is ambiguous; check remote before retrying')
    return dict(plan,state='PUBLISHED_AND_REF_VERIFIED',commit=commit)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--public',action='store_true');a=p.parse_args()
    print(json.dumps(run(ROOT,apply=a.apply,public=a.public),ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except (PublishError,PackageError,RuntimeError,ValueError) as e:
        print('PUBLISH_BLOCKED: '+str(e),file=sys.stderr);sys.exit(2)
