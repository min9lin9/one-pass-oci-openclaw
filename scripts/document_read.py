#!/usr/bin/env python3
from __future__ import annotations
import json, os, pathlib, subprocess, sys

def resolve_inside(value, root):
    p=pathlib.Path(value).expanduser().resolve()
    if not p.is_relative_to(root): raise ValueError('File path is outside the authorized workspace')
    return p

def main():
    if len(sys.argv)!=3: raise ValueError('Usage: document_read.py INPUT OUTPUT')
    home=pathlib.Path.home(); root=(home/'.openclaw-operations/workspace').resolve()
    src=resolve_inside(sys.argv[1],root); dst=resolve_inside(sys.argv[2],root)
    if src==dst or dst.exists(): raise ValueError('Output must be a new separate file')
    if src.suffix.lower() not in ('.pdf','.docx','.pptx','.xlsx','.xls','.html','.txt','.md','.csv'):
        raise ValueError('Format not in the local-reader allowlist')
    if not src.is_file() or src.stat().st_size>50*1024*1024: raise ValueError('Missing or oversized input')
    paths=json.loads((home/'.local/state/oracle-ai-stack/runtime-paths.json').read_text())
    dst.parent.mkdir(parents=True,exist_ok=True)
    env={'HOME':str(home),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONNOUSERSITE':'1'}
    code='from markitdown import MarkItDown; import sys; r=MarkItDown(enable_plugins=False).convert_local(sys.argv[1]); open(sys.argv[2],"x",encoding="utf-8").write(r.text_content)'
    subprocess.run([paths['markitdown_python'],'-c',code,str(src),str(dst)],env=env,check=True,timeout=120)
    print('EXTRACTED_LOCAL_MARKDOWN: '+str(dst))
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('LOCAL_READER_FAILED: '+type(e).__name__,file=sys.stderr); sys.exit(2)
