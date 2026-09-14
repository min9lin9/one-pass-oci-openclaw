#!/usr/bin/env python3
"""Root-only human/operator entrypoint. NOT in an agent sudo allowlist.
Reads each profile's protected provider environment before dropping privileges.
"""
import argparse, os, pwd, subprocess
from profile_spec import get_profile, environment
from profiles_runtime import credentials
from stacklib import StackError

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['oauth','status','catalog']);p.add_argument('--profile',required=True,choices=['operations','planning','development']);p.add_argument('--provider',default='openai',choices=['openai','opencode','opencode-go']);a=p.parse_args()
    if os.geteuid()!=0: raise StackError('Operator/root required')
    spec=get_profile(a.profile);env=environment(spec);env.update(credentials(spec));u=pwd.getpwnam(spec.user)
    args=['models','auth','--agent',spec.agent,'login','--provider','openai','--device-code'] if a.action=='oauth' else (['models','list','--provider',a.provider,'--json'] if a.action=='catalog' else ['models','status','--agent',spec.agent,'--check'])
    from contextlib import nullcontext
    from profiles_runtime import exclusive_profile_state
    def demote():
        os.initgroups(spec.user,u.pw_gid);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
    with exclusive_profile_state(spec) if a.action=='oauth' else nullcontext():
        if a.action=='oauth':
            from profiles_runtime import invalidate_model
            invalidate_model(spec, 'OAUTH_REAUTHENTICATION_PENDING')
        code=subprocess.call([str(spec.binary),'--profile',spec.name,*args],cwd=spec.workspace,env=env,preexec_fn=demote)
    raise SystemExit(code)
if __name__=='__main__':
    from operator_lock import locked
    with locked(): main()
