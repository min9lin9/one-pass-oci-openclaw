#!/usr/bin/env python3
"""Stage immutable Git snapshots, seal a review receipt, install selected skills.

No upstream setup/hook is ever invoked by stage or seal. A receipt is an audit
record, not cryptographic proof that a human/LLM review was correct.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, pathlib, re, shutil, stat, sys, tarfile, tempfile
from datetime import datetime, timezone
from stacklib import StackError, atom_json, digest_tree, repo_name, run, SHA_RE, NAME_RE
ROOT = pathlib.Path(__file__).resolve().parents[1]


def safe_extract(blob: bytes, dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    count = size = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:*') as tf:
        for m in tf:
            p = pathlib.PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or m.issym() or m.islnk() or not (m.isfile() or m.isdir()):
                raise StackError('Source archive has unsafe paths, links, or special files')
            if '.git' in p.parts: continue
            count += 1; size += m.size
            if count > 40000 or size > 512 * 1024 * 1024 or m.size > 64 * 1024 * 1024:
                raise StackError('Source exceeds bounded staging budget; use a reviewed subset')
            target = dest.joinpath(*p.parts)
            if m.isdir(): target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = tf.extractfile(m)
                if stream is None: raise StackError('Unreadable archive member')
                target.write_bytes(stream.read())
                target.chmod(0o755 if m.mode & 0o111 else 0o644)


def snapshot(repo: str, ref: str, dest: pathlib.Path) -> str:
    repo_name(repo)
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or ref.startswith('-'):
        raise StackError('Invalid source ref')
    if dest.exists(): raise StackError('Staging destination exists; never silently overwrite it')
    with tempfile.TemporaryDirectory(prefix='oracle-source-') as td:
        td = pathlib.Path(td)
        env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='0')
        run(['git','-c','core.hooksPath=/dev/null','-c','init.templateDir=/dev/null','init','-q',str(td)], env=env)
        run(['git','-C',str(td),'remote','add','origin',f'https://github.com/{repo}.git'], env=env)
        run(['git','-C',str(td),'-c','core.hooksPath=/dev/null','fetch','--depth=1','origin',ref], env=env)
        sha = run(['git','-C',str(td),'rev-parse','FETCH_HEAD^{commit}'], env=env).stdout.decode().strip()
        if not SHA_RE.fullmatch(sha): raise StackError('Not a commit SHA')
        blob = run(['git','-C',str(td),'archive','--format=tar',sha], env=env,max_output=512*1024*1024).stdout
        safe_extract(blob, dest)
    return sha


def inventory(root: pathlib.Path) -> dict:
    # Signals guide review; they are not an allow/deny scanner or a safety claim.
    signals = {k:[] for k in ('executables','hooks','installers','credential_references','external_writes')}
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel = p.relative_to(root).as_posix()
        if p.suffix in ('.sh','.py','.js','.ts','.mjs') or p.stat().st_mode & stat.S_IXUSR:
            signals['executables'].append(rel)
        if 'hook' in rel.lower() or p.name in ('settings.json','.mcp.json'):
            signals['hooks'].append(rel)
        if p.name in ('package.json','setup.py','pyproject.toml','requirements.txt','setup.sh','setup','Dockerfile'):
            signals['installers'].append(rel)
        if p.stat().st_size < 1024*1024 and p.suffix in ('.md','.py','.sh','.json','.ts','.mjs'):
            text = p.read_text(errors='replace')
            if re.search(r'CLAUDE_PLUGIN_ROOT|auth\.json|API_KEY|PRIVATE_KEY|credential', text, re.I):
                signals['credential_references'].append(rel)
            if re.search(r'user/starred|git push|auto.?publish|--dangerously|skipDangerous', text, re.I):
                signals['external_writes'].append(rel)
    return signals


def source_subpath(value: str) -> str:
    """Validate catalog paths too; safe archives alone do not validate a manifest."""
    p=pathlib.PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value or '\x00' in value:
        raise StackError('Invalid source subpath')
    return value


def validate_catalog_item(item: dict) -> None:
    if not NAME_RE.fullmatch(item.get('id','')): raise StackError('Invalid catalog source ID')
    repo_name(item['repo'])
    for value in item.get('skills',[]): source_subpath(value)
    if item.get('source_path'): source_subpath(item['source_path'])
    if item.get('adapter') and not NAME_RE.fullmatch(item['adapter']):
        raise StackError('Invalid adapter name')


def stage(manifest: pathlib.Path, target: pathlib.Path) -> None:
    spec = json.loads(manifest.read_text())
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (target/'sources.lock.json').exists():
        raise StackError('Stage already locked. Reuse it or create a new directory for updates')
    records=[]
    for item in spec['sources']:
        validate_catalog_item(item)
        print('STAGING ' + item['id'], flush=True)
        source = target/'sources'/item['id']
        sha = snapshot(item['repo'], item['ref'], source)
        for sub in item.get('skills',[]):
            if not (source/sub/'SKILL.md').is_file():
                raise StackError(f"{item['id']}: expected SKILL.md missing; upstream layout changed")
        expected = item.get('source_path')
        if expected and not (source/expected).exists(): raise StackError('Source layout changed')
        licenses = [p.relative_to(source).as_posix() for p in source.glob('LICENSE*') if p.is_file()]
        if not licenses: raise StackError(item['id'] + ': license missing; review separately')
        records.append(dict(item, commit=sha, tree_sha256=digest_tree(source), licenses=licenses,
                            signals=inventory(source)))
    atom_json(target/'sources.lock.json', {'schema':1,'created_utc':datetime.now(timezone.utc).isoformat(),
              'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'sources':records})
    print('STAGED_NOT_REVIEWED: inspect README, selected SKILL.md, runtime code and license before sealing')


def verify_stage(target: pathlib.Path, reviewed: bool = True) -> dict:
    lockpath=target/'sources.lock.json'
    lock=json.loads(lockpath.read_text())
    if reviewed:
        receipt=json.loads((target/'review.receipt.json').read_text())
        if receipt['lock_sha256'] != hashlib.sha256(lockpath.read_bytes()).hexdigest():
            raise StackError('Review receipt is stale')
    for item in lock['sources']:
        validate_catalog_item(item)
        if not SHA_RE.fullmatch(item['commit']): raise StackError('Unpinned source')
        if digest_tree(target/'sources'/item['id']) != item['tree_sha256']:
            raise StackError('Staged source changed after pin/review: '+item['id'])
    return lock


def seal(target: pathlib.Path, note: pathlib.Path) -> None:
    verify_stage(target, reviewed=False)
    text=note.read_text()
    if len(text.strip()) < 100: raise StackError('Provide substantive code/permission/license review notes')
    atom_json(target/'review.receipt.json', {
        'lock_sha256':hashlib.sha256((target/'sources.lock.json').read_bytes()).hexdigest(),
        'review_notes_sha256':hashlib.sha256(note.read_bytes()).hexdigest(),
        'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'warning':'Reviewer assertion; not a proof of safety or an execution test'})
    shutil.copyfile(note, target/'review-notes.md')
    print('REVIEW_RECEIPT_WRITTEN')


def parse_name(skill: pathlib.Path) -> str:
    text=skill.read_text()
    if not text.startswith('---\n'): raise StackError('SKILL.md requires YAML frontmatter')
    front=text.split('---',2)[1]
    m=re.search(r'^name:\s*[\'\"]?([a-z0-9-]+)[\'\"]?\s*$',front,re.M)
    if not m or not NAME_RE.fullmatch(m[1]): raise StackError('Invalid skill name')
    if not re.search(r'^description:',front,re.M): raise StackError('Skill has no description')
    return m[1]


def install_one(source: pathlib.Path, dest: pathlib.Path, receipt: dict, prior: dict) -> dict:
    name=parse_name(source/'SKILL.md')
    dst=dest/name
    source_hash=digest_tree(source)
    if dst.exists():
        if dst.is_symlink(): raise StackError('Refusing to overwrite symlink skill '+name)
        actual=digest_tree(dst)
        old=prior.get(name)
        if old is None or actual != old.get('installed_sha256'):
            raise StackError('Local/unmanaged edits detected: '+name+'; preserve and review before replacing')
        if actual == source_hash: return dict(receipt, installed_sha256=actual, state='INSTALLED_NOT_RUNTIME_VERIFIED')
    temp=pathlib.Path(tempfile.mkdtemp(prefix='.'+name+'-',dir=dest))
    shutil.rmtree(temp); shutil.copytree(source,temp)
    backup=dest.parent/'skill-backups'/receipt['commit']/name
    backup.parent.mkdir(parents=True,exist_ok=True)
    try:
        if dst.exists():
            if backup.exists(): raise StackError('Rollback path exists; refusing to erase it')
            os.replace(dst,backup)
        os.replace(temp,dst)
    except Exception:
        if backup.exists() and not dst.exists(): os.replace(backup,dst)
        raise
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return dict(receipt, installed_sha256=digest_tree(dst), state='INSTALLED_NOT_RUNTIME_VERIFIED')


def apply(target: pathlib.Path, home: pathlib.Path) -> None:
    lock=verify_stage(target)
    dest=home/'.openclaw-operations/workspace/skills'; dest.mkdir(parents=True,exist_ok=True)
    state=home/'.local/state/oracle-ai-stack/extensions.json'
    previous=json.loads(state.read_text()) if state.exists() else {}
    installed=dict(previous)
    runtime_home=home/'.local/share/oracle-ai-stack/sources'
    runtime_home.mkdir(parents=True,exist_ok=True)
    for item in lock['sources']:
        src=target/'sources'/item['id']
        runtime=runtime_home/item['id']/item['commit']
        if not runtime.exists():
            runtime.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(src,runtime)
        elif digest_tree(runtime) != item['tree_sha256']:
            # Build products live outside these immutable snapshots.
            raise StackError('Runtime source snapshot modified: '+item['id'])
        r={'repo':item['repo'],'commit':item['commit'],'source_id':item['id']}
        for sub in item.get('skills',[]):
            name=parse_name(src/sub/'SKILL.md')
            installed[name]=install_one(src/sub,dest,r,previous)
            atom_json(state,installed)
        if item.get('adapter'):
            adapter=ROOT/'adapters'/item['adapter']
            name=parse_name(adapter/'SKILL.md')
            installed[name]=install_one(adapter,dest,r,previous)
        atom_json(state,installed)
    atom_json(home/'.local/state/oracle-ai-stack/source-paths.json', {
        i['id']:str(runtime_home/i['id']/i['commit']) for i in lock['sources']})
    print(json.dumps({'skills_installed':len(installed),'state':'RUNTIME_CHECKS_REQUIRED'}))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action', choices=['stage','seal','verify','apply'])
    p.add_argument('--stage',type=pathlib.Path,required=True)
    p.add_argument('--manifest',type=pathlib.Path,default=ROOT/'manifests/extensions.json')
    p.add_argument('--review-notes',type=pathlib.Path)
    p.add_argument('--home',type=pathlib.Path,default=pathlib.Path.home())
    a=p.parse_args()
    if a.action=='stage': stage(a.manifest,a.stage)
    elif a.action=='seal':
        if not a.review_notes: p.error('--review-notes required')
        seal(a.stage,a.review_notes)
    elif a.action=='verify': verify_stage(a.stage); print('SOURCE_INTEGRITY_OK')
    else: apply(a.stage,a.home)

if __name__=='__main__':
    try: main()
    except (StackError,FileNotFoundError,KeyError,ValueError) as e:
        print('BLOCKED: '+str(e),file=sys.stderr); sys.exit(2)
