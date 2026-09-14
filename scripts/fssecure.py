"""Descriptor-anchored writes for installer-owned files on POSIX systems.

Never follow parent/target symlinks, never truncate an existing inode, and never
use a predictable temporary name. This reduces file-redirection attacks; it is
not a sandbox against a privileged process or a malicious kernel.
"""
from __future__ import annotations
import contextlib
import os
import pathlib
import secrets
import stat

class FileSafetyError(RuntimeError):
    pass

@contextlib.contextmanager
def directory(path, *, create=False, mode=0o700):
    raw=os.fspath(path)
    if '..' in pathlib.PurePath(raw).parts:
        raise FileSafetyError('Parent traversal in managed path')
    p=pathlib.Path(os.path.abspath(raw))
    flags=os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd=os.open('/',flags)
    try:
        for part in p.parts[1:]:
            if create:
                try: os.mkdir(part,mode,dir_fd=fd)
                except FileExistsError: pass
            next_fd=os.open(part,flags,dir_fd=fd)
            os.close(fd); fd=next_fd
        yield fd
    except OSError as exc:
        raise FileSafetyError('Managed directory is unavailable or contains a link') from exc
    finally:
        os.close(fd)

def write_text(path, text, *, mode=0o600, uid=None, gid=None):
    p=pathlib.Path(path)
    if not p.name or p.name in ('.','..'):
        raise FileSafetyError('Invalid managed filename')
    with directory(p.parent,create=True) as parent:
        try:
            current=os.stat(p.name,dir_fd=parent,follow_symlinks=False)
        except FileNotFoundError: current=None
        if current and (not stat.S_ISREG(current.st_mode) or current.st_nlink!=1):
            raise FileSafetyError('Managed target must be a single-link regular file')
        tmp='.'+p.name+'.'+secrets.token_hex(12)
        fd=None
        try:
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=parent)
            with os.fdopen(fd,'w',encoding='utf-8') as output:
                fd=None
                output.write(text); output.flush()
                os.fchmod(output.fileno(),mode)
                if uid is not None: os.fchown(output.fileno(),uid,gid if gid is not None else -1)
                os.fsync(output.fileno())
            os.replace(tmp,p.name,src_dir_fd=parent,dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            if fd is not None: os.close(fd)
            try: os.unlink(tmp,dir_fd=parent)
            except FileNotFoundError: pass

def chown_tree(path,uid,gid):
    with directory(path) as root:
        for _, dirs, files, fd in os.fwalk('.',dir_fd=root,follow_symlinks=False):
            os.fchown(fd,uid,gid)
            for name in files:
                info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode): continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                    raise FileSafetyError('Unexpected linked or special file in managed tree')
                f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                try:
                    actual=os.fstat(f)
                    if not stat.S_ISREG(actual.st_mode) or actual.st_nlink!=1:
                        raise FileSafetyError('Managed file changed during ownership check')
                    os.fchown(f,uid,gid)
                finally: os.close(f)
