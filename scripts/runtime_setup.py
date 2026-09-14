#!/usr/bin/env python3
"""Install optional libraries into per-tool directories, only as unprivileged UID.
Source review must happen before invoking this script. No secret values are inputs.
"""
import json, os, pathlib, shutil, sys
from stacklib import StackError, atom_json, run

def main():
    if os.geteuid()==0: raise StackError('Do not build extension runtimes as root')
    home=pathlib.Path.home(); state=home/'.local/state/oracle-ai-stack'
    sources=json.loads((state/'source-paths.json').read_text())
    base=home/'.local/share/oracle-ai-stack/runtime'; base.mkdir(parents=True,exist_ok=True)
    node=home/'.local/lib/openclaw-cli/tools/node/bin/node'
    npm=node.parent/'npm'
    if not node.exists(): raise StackError('Private Node runtime not found; inspect official installer prefix')
    env=dict(os.environ,PATH=str(node.parent)+':/usr/bin:/bin',NPM_CONFIG_AUDIT='false',NPM_CONFIG_FUND='false')
    info={'node':str(node),'gstack_full':'NOT_CONFIGURED_NATIVE_METHODS_ONLY'}
    md=base/'markitdown'; md.mkdir(exist_ok=True)
    py=md/'venv/bin/python'
    if not py.exists(): run(['/usr/bin/python3','-m','venv',str(md/'venv')])
    source=pathlib.Path(sources['markitdown'])/'packages/markitdown'
    work=md/pathlib.Path(sources['markitdown']).name
    if not work.exists(): shutil.copytree(source,work)
    report=md/('installed-'+work.name+'.json')
    if not report.exists():
        run([str(py),'-m','pip','install','--report',str(report),str(work)+'[pdf,docx,pptx,xlsx]'],env=env,timeout=1200)
    run([str(py),'-c','from markitdown import MarkItDown; print("OK")'],env=env)
    info['markitdown_python']=str(py)
    (md/'requirements.resolved.txt').write_bytes(run([str(py),'-m','pip','freeze'],env=env).stdout)

    pretty=base/'pretty-mermaid'/pathlib.Path(sources['pretty-mermaid']).name
    if not pretty.exists(): pretty.parent.mkdir(parents=True,exist_ok=True); shutil.copytree(sources['pretty-mermaid'],pretty)
    if not (pretty/'package.json').is_file(): raise StackError('Pretty Mermaid layout changed; inspect dependency script')
    if not (pretty/'.oas-installed').exists():
        cmd='ci' if (pretty/'package-lock.json').is_file() else 'install'
        run([str(npm),cmd,'--ignore-scripts','--no-audit','--no-fund'],cwd=pretty,env=env,timeout=900)
        (pretty/'.oas-installed').write_text('reviewed runtime dependencies resolved\n')
    # Prevent unreviewed automatic package downloads during the smoke run.
    offline=dict(env,NPM_CONFIG_OFFLINE='true',NPM_CONFIG_IGNORE_SCRIPTS='true')
    (pretty/'oas-smoke.mmd').write_text('graph LR\n  A[Input] --> B[Checked]\n')
    run([str(node),str(pretty/'scripts/render.mjs'),'--input',str(pretty/'oas-smoke.mmd'),
         '--output',str(pretty/'oas-smoke.svg'),'--theme','github-light'],cwd=pretty,env=offline)
    if '<svg' not in (pretty/'oas-smoke.svg').read_text(): raise StackError('No SVG produced')
    info['pretty_mermaid']=str(pretty)

    mcp=base/'mcporter'; mcp.mkdir(exist_ok=True)
    if not (mcp/'node_modules/.bin/mcporter').exists():
        run([str(npm),'install','--prefix',str(mcp),'--save-exact','--ignore-scripts','mcporter@0.11.0'],env=env,timeout=900)
    # This runtime is the official registry package, not a build of the user's fork.
    # Record that distinction rather than claiming the fork's code is running.
    info['mcporter']=str(mcp/'node_modules/.bin/mcporter')
    info['mcporter_origin']='npm:mcporter@0.11.0; min9lin9 fork retained as source reference'
    isolated=home/'.local/share/oracle-ai-stack/mcp-home'
    cfg=isolated/'config/mcporter.json'
    if not cfg.exists(): atom_json(cfg,{'mcpServers':{},'imports':[]})
    run([info['mcporter'],'--version'],env=env)
    atom_json(state/'runtime-paths.json',info)
    atom_json(state/'runtime-checks.json',{'markitdown_import':'PASS','pretty_mermaid_svg':'PASS',
              'mcporter_cli':'PASS','mcp_external_connections':'NOT_CONFIGURED','gstack_full':'NOT_CONFIGURED'})
    print('EXTENSION_RUNTIME_SMOKES_OK; external services/auth and full gstack are separate checks')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('RUNTIME_SETUP_BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
