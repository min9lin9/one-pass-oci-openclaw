#!/usr/bin/env python3
import json, pathlib, shutil, sys, os
from stacklib import run, atom_json, StackError, digest_tree

def main():
    home=pathlib.Path.home()
    if str(home)!='/home/clawfetch' or os.geteuid()==0: raise StackError('Run as clawfetch')
    if len(sys.argv)!=2: raise StackError('Pass reviewed insane-search snapshot path')
    source=pathlib.Path(sys.argv[1])/'skills/insane-search'
    source_hash=digest_tree(source)
    work=home/'engine-sources'/source_hash
    # Immutable versions: an in-flight reader retains its source on upgrades.
    work.parent.mkdir(parents=True,exist_ok=True)
    if not work.exists(): shutil.copytree(source,work)
    elif digest_tree(work)!=source_hash: raise StackError('Reader source was modified')
    venv=home/'venv'; py=venv/'bin/python'
    if not py.exists(): run(['/usr/bin/python3','-m','venv',str(venv)])
    if not (home/'dependencies.resolved.json').exists():
        run([str(py),'-m','pip','install','--report',str(home/'dependencies.resolved.json'),
             'curl_cffi','PyYAML','beautifulsoup4','markdownify','requests','httpx','yt-dlp','playwright','pypdf'],timeout=1200)
        (home/'requirements.resolved.txt').write_bytes(run([str(py),'-m','pip','freeze']).stdout)
    env={'HOME':str(home),'PATH':str(venv/'bin')+':/usr/bin:/bin','LANG':'C.UTF-8',
         'PYTHONDONTWRITEBYTECODE':'1','INSANE_SEARCH_XAI':'off','PLAYWRIGHT_BROWSERS_PATH':str(home/'browsers')}
    # Download browser only once; system libraries are operator-installed separately.
    if not (home/'browser-installed').exists():
        run([str(py),'-m','playwright','install','chromium'],env=env,timeout=1200)
        (home/'browser-installed').touch()
    run([str(py),'-m','engine','--help'],cwd=work,env=dict(env,PIP_NO_INDEX='1',UV_OFFLINE='1'))
    atom_json(home/'runtime.json',{'python':str(py),'engine':str(work),'source_sha256':source_hash})
    print('INSANE_ENGINE_CLI_OK; public fetch and private-address rejection still need smoke tests')
if __name__=='__main__':
    try: main()
    except Exception as e:
        print('FETCH_RUNTIME_BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
