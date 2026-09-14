"""Common root maintenance lock shared by upload/install/auth/backup commands."""
import contextlib, fcntl, os, stat
from stacklib import StackError

PATH='/run/lock/oracle-ai-stack-operator.lock'
@contextlib.contextmanager
def locked():
    fd=os.open(PATH,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        meta=os.fstat(fd)
        if meta.st_uid!=0 or meta.st_nlink!=1 or not stat.S_ISREG(meta.st_mode):
            raise StackError('Invalid operator lock ownership/type')
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc: raise StackError('Another deployment/maintenance action is active') from exc
        yield
    finally: os.close(fd)
