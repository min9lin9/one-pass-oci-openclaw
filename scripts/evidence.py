"""Fail-closed interpretation of observed OpenClaw JSON, not arbitrary text search.
Unknown schemas stay unverified. A model marker is not evidence of file safety,
HTTPS delivery, persistent memory, or successful implementation of a real task.
"""
from __future__ import annotations
import json

def layers(value):
    if not isinstance(value,dict): return []
    result=[value]
    if isinstance(value.get('result'),dict): result.append(value['result'])
    return result

def successful_response(value,returncode=0):
    nodes=layers(value)
    if returncode!=0 or not nodes: return False
    for item in nodes:
        if item.get('ok') is False or item.get('error') or item.get('aborted'): return False
        status=item.get('status')
        if status is not None and status not in ('ok','completed','success'): return False
        meta=item.get('meta',{})
        if not isinstance(meta,dict) or meta.get('error') or meta.get('aborted'): return False
        if meta.get('stopReason') in ('error','aborted','timeout'): return False
        payloads=item.get('payloads',[])
        if not isinstance(payloads,list): return False
        if any(not isinstance(p,dict) or p.get('isError') or p.get('error') for p in payloads): return False
    return any(isinstance(item.get('payloads'),list) and item['payloads'] for item in nodes)

def assistant_texts(value):
    if not successful_response(value): return []
    # Prefer the inner canonical result; do not count duplicate outer projections.
    for item in reversed(layers(value)):
        if isinstance(item.get('payloads'),list):
            return [p['text'] for p in item['payloads'] if isinstance(p.get('text'),str)]
    return []

def exact_marker(value,marker,returncode=0):
    return successful_response(value,returncode) and '\n'.join(assistant_texts(value)).strip()==marker

def model_identity(value):
    for item in reversed(layers(value)):
        meta=item.get('meta',{})
        agent=meta.get('agentMeta',{}) if isinstance(meta,dict) else {}
        for candidate in (agent,item):
            if isinstance(candidate,dict) and isinstance(candidate.get('provider'),str) and isinstance(candidate.get('model'),str):
                return candidate['provider'],candidate['model']
    return None,None

def selected_model_observed(value,provider,model):
    actual_provider,actual_model=model_identity(value)
    return actual_provider==provider and actual_model in (model,model.split('/',1)[-1])

def delegation_receipt(path):
    if not path.exists(): return 'NOT_TESTED'
    try: report=json.loads(path.read_text())
    except (OSError,ValueError): return 'INVALID_RECEIPT'
    rows=report.get('profiles',{}) if isinstance(report,dict) else {}
    ok=(report.get('state')=='DELEGATION_MARKERS_PASSED' and set(rows)=={'planning','development'}
        and all(isinstance(v,dict) and v.get('marker_roundtrip')=='PASS' for v in rows.values()))
    return 'MARKER_TEST_PASSED_NOT_FULL_TASK_E2E' if ok else 'FAILED_OR_INCOMPLETE'
