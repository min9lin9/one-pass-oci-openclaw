"""Install only the local operations adapters as the unprivileged operations UID."""
import json, os, pathlib, pwd
from extensions import install_one
from profile_spec import get_profile
from stacklib import atom_json, StackError

def main():
    p=get_profile('operations')
    if os.getuid()!=pwd.getpwnam(p.user).pw_uid: raise StackError('Run as operations, never as root')
    base=pathlib.Path('/opt/oracle-ai-stack');receipt=p.home/'.local/state/oracle-ai-stack/ops-adapters.json'
    prior=json.loads(receipt.read_text()) if receipt.exists() else {};installed=dict(prior)
    for name in ('operations-orchestrator','gbrain-memory'):
        installed[name]=install_one(base/'adapters'/name,p.workspace/'skills',
            {'source_id':'local-v0.4','repo':'min9lin9/one-pass-oci-openclaw','commit':'local'},prior)
    atom_json(receipt,installed)
if __name__=='__main__':main()
