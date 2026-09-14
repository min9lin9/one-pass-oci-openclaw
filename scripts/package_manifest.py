"""Explicit redistributable file allowlist. Runtime state/secrets are never selected."""
from __future__ import annotations
import hashlib, json, pathlib, re

ROOT_FILES={'README.md','SKILL.md','AGENTS.md','LICENSE','SECURITY.md','THIRD_PARTY_NOTICES.md',
            'CHANGELOG.md','TEST-REPORT.md','REVIEW.md','.gitignore','VERSION'}
ROOT_DIRS={'scripts','tests','adapters','agents','manifests','references','templates','.github'}
EXTENSIONS={'.py','.sh','.md','.json','.yaml','.yml','.example'}
DENY_NAMES={'.env','secrets.env','auth.json','auth-profiles.json','review-notes.md'}
MANIFEST='PACKAGE-MANIFEST.json'
# These are supplemental tripwires, not a proof that arbitrary text contains no secrets.
SECRET_PATTERNS=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
                 re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
                 re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
                 re.compile(r'\btskey-(?:auth|api)-[A-Za-z0-9_-]{20,}\b')]

class PackageError(RuntimeError):pass

def selected(root):
    root=pathlib.Path(root);result=[]
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root)
        if any(part in ('.git','__pycache__','.pytest_cache') for part in rel.parts):continue
        if path.is_symlink():raise PackageError('Symlinks are not publishable')
        if not path.is_file():continue
        allowed=(len(rel.parts)==1 and rel.name in ROOT_FILES) or (rel.parts[0] in ROOT_DIRS and path.suffix in EXTENSIONS)
        if not allowed:continue
        if path.name in DENY_NAMES or path.suffix in ('.pem','.key','.p12') or path.stat().st_nlink!=1:
            raise PackageError('Potential secret or hardlink in publishable files')
        blob=path.read_bytes()
        if len(blob)>2*1024*1024:raise PackageError('Unexpected oversized source file')
        try:text=blob.decode('utf-8')
        except UnicodeError as exc:raise PackageError('Only reviewed UTF-8 source files are publishable') from exc
        if any(p.search(text) for p in SECRET_PATTERNS):raise PackageError('Potential credential material; inspect privately')
        result.append((rel.as_posix(),blob,path.stat().st_mode & 0o111))
    return result

def build(root):
    return {'schema':1,'repository':'min9lin9/one-pass-oci-openclaw',
            'files':{name:{'sha256':hashlib.sha256(blob).hexdigest(),'executable':bool(mode)} for name,blob,mode in selected(root)}}

def verify(root):
    path=pathlib.Path(root)/MANIFEST
    if path.is_symlink() or not path.is_file():raise PackageError('Package manifest missing or linked')
    expected=json.loads(path.read_text())
    if expected!=build(root):raise PackageError('Package differs from its reviewed file manifest; review and regenerate before publishing')
    return expected
