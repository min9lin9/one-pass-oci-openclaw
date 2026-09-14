"""Shared validation; never source a secrets file or print subprocess arguments."""
from __future__ import annotations
import hashlib, ipaddress, json, os, pathlib, re, shlex, subprocess, tempfile, urllib.request, urllib.error
from typing import Any
from process_guard import ProcessBudgetError

class StackError(RuntimeError):
    pass

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

def repo_name(value: str) -> str:
    if not REPO_RE.fullmatch(value) or any(x in ('..', '.') for x in value.split('/')):
        raise StackError('Invalid owner/repository identifier')
    return value

def domain_name(value: str) -> str:
    value = value.lower().rstrip('.')
    parts = value.split('.')
    if len(parts) < 2 or len(value) > 253 or not all(NAME_RE.fullmatch(p) and not p.endswith('-') for p in parts):
        raise StackError('DOMAIN must be a plain DNS name, not a URL, wildcard, path, or IP')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise StackError('An IP address is not a domain')

def private_file(path: pathlib.Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StackError('Secret path must be a regular file, not a symlink')
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise StackError('Secrets file must have mode 0600 (parent directory 0700 recommended)')

def load_env(path: str | pathlib.Path) -> dict[str, str]:
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        raise StackError('Local secrets file is missing; copy templates/secrets.env.example')
    private_file(p)
    out: dict[str, str] = {}
    for n, raw in enumerate(p.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key.strip()):
            raise StackError(f'Invalid secrets file syntax at line {n}')
        key = key.strip()
        if key in out:
            raise StackError(f'Duplicate setting: {key}')
        tokens = shlex.split(value, comments=True, posix=True)
        if len(tokens) > 1:
            raise StackError(f'Quote values containing spaces at line {n}')
        out[key] = tokens[0] if tokens else ''
    if out.get('DOMAIN'):
        out['DOMAIN'] = domain_name(out['DOMAIN'])
    out.setdefault('ORACLE_SSH_USER', 'ubuntu')
    out.setdefault('SSH_PORT', '22')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', out['ORACLE_SSH_USER']):
        raise StackError('Invalid SSH user')
    if not out['SSH_PORT'].isdigit() or not 1 <= int(out['SSH_PORT']) <= 65535:
        raise StackError('Invalid SSH port')
    if out.get('ORACLE_HOST'):
        try:
            ipaddress.ip_address(out['ORACLE_HOST'])
        except ValueError:
            domain_name(out['ORACLE_HOST'])
    return out

def require(cfg: dict, *keys: str) -> None:
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        raise StackError('Missing settings (names only): ' + ', '.join(missing))

def atom_json(path: pathlib.Path, obj: Any, mode: int = 0o600) -> None:
    from fssecure import write_text, FileSafetyError
    try: write_text(path, json.dumps(obj,ensure_ascii=False,indent=2)+'\n',mode=mode)
    except FileSafetyError as exc: raise StackError(str(exc)) from exc


def run(args: list[str], *, cwd=None, env=None, data: bytes | None = None,
        timeout: int = 900, check: bool = True, max_output: int = 8*1024*1024) -> subprocess.CompletedProcess:
    try:
        from process_guard import run_bounded
        p = run_bounded(args, cwd=cwd, env=env, input=data, timeout=timeout,max_output=max_output)
    except ProcessBudgetError as e:
        raise StackError(str(e)) from e
    except subprocess.TimeoutExpired as e:
        raise StackError('Subprocess exceeded its time budget; raw output withheld. Use a private diagnostic capture if needed') from e
    except FileNotFoundError as e:
        raise StackError('A required executable is missing: ' + pathlib.Path(args[0]).name) from e
    if check and p.returncode:
        # Deliberately do not include args, stdout/stderr, tokens, or URL query strings.
        raise StackError(f'{pathlib.Path(args[0]).name} failed with exit code {p.returncode}; no raw output disclosed')
    return p

def digest_tree(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise StackError('Symlink in source tree is not allowed by this installer')
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b'\0')
            h.update(str(p.stat().st_mode & 0o111).encode()+b'\0')
            h.update(p.read_bytes())
    return h.hexdigest()

def cf_request(token: str, method: str, path: str, body=None):
    req = urllib.request.Request('https://api.cloudflare.com/client/v4' + path,
          data=None if body is None else json.dumps(body).encode(), method=method,
          headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.load(r)
    except urllib.error.HTTPError as e:
        raise StackError(f'Cloudflare HTTP {e.code}; check token scopes/zone (response withheld)') from e
    if not result.get('success'):
        raise StackError('Cloudflare rejected the request; response withheld')
    return result

def tailnet_ipv4(value: str) -> str:
    try: ip = ipaddress.ip_address(value)
    except ValueError as e: raise StackError('Missing or invalid Tailscale IPv4') from e
    if not isinstance(ip, ipaddress.IPv4Address) or ip not in ipaddress.ip_network('100.64.0.0/10'):
        raise StackError('Address is not in the Tailscale IPv4 range')
    return str(ip)
