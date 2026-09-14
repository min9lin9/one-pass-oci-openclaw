"""Operator-triggered live delegation acceptance. This consumes model usage.
No user files, production services or external publication are touched. Receipts
separate CLI, model/tool behavior and Buzz/new-conversation tests.
"""
import json,pathlib,uuid
from evidence import exact_marker
from stacklib import StackError,atom_json
from profile_spec import PROFILES
from profiles_runtime import as_user,STATE,BASE

def smoke():
    op=PROFILES['operations'];results={}
    for name in ('planning','development'):
        task=str(uuid.uuid4());marker='oas-accept-'+uuid.uuid4().hex
        prompt='Acceptance test. Reply with exactly this literal marker and nothing else: '+marker
        plan='Approved installation smoke only: no shell, no file writes, no network calls; return the literal marker.' if name=='development' else ''
        req={'task_id':task,'action':'run','prompt':prompt,'approved_plan':plan}
        out=as_user(op,['/usr/bin/python3',BASE/'scripts/dispatch.py','--profile',name],data=json.dumps(req).encode(),timeout=760,check=False)
        try:r=json.loads(out.stdout)
        except ValueError:r={'state':'BRIDGE_OR_AUTH_FAILED'}
        observed=r.get('state')=='COMPLETED' and exact_marker(r.get('response',{}),marker)
        results[name]={'task_id':task,'marker_roundtrip':'PASS' if observed else 'FAIL','worker_state':r.get('state'),'filesystem_policy_test':'NOT_TESTED'}
    report={'state':'DELEGATION_MARKERS_PASSED' if all(x['marker_roundtrip']=='PASS' for x in results.values()) else 'DELEGATION_INCOMPLETE',
            'profiles':results,'native_buzz_roundtrip':'NOT_TESTED','planning_read_only_enforcement':'CONFIGURED_NOT_LIVE_ADVERSARIALLY_TESTED','development_filesystem':'NOT_TESTED'}
    atom_json(STATE/'acceptance.json',report);return report
