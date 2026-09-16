"""Bounded capture and process-group cleanup, without printing arguments/output.
Killing a CLI does NOT prove that a remote Gateway cancelled an accepted task.
"""
from __future__ import annotations
import os, selectors, signal, subprocess, tempfile, time

class ProcessBudgetError(RuntimeError):
    pass

def run_bounded(args, *, input=None, cwd=None, env=None, timeout=900,
                preexec_fn=None, max_output=8*1024*1024, termination_grace=2):
    buffers={}; proc=None
    with tempfile.TemporaryFile() as incoming, selectors.DefaultSelector() as selector:
        if input: incoming.write(input)
        incoming.seek(0)
        proc=subprocess.Popen(args,stdin=incoming,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            cwd=cwd,env=env,preexec_fn=preexec_fn,start_new_session=True)
        for stream in (proc.stdout,proc.stderr):
            buffers[stream]=bytearray();selector.register(stream,selectors.EVENT_READ)
        deadline=time.monotonic()+timeout
        try:
            while selector.get_map():
                remaining=deadline-time.monotonic()
                if remaining<=0: raise ProcessBudgetError('Subprocess deadline exceeded; remote completion may be uncertain')
                for key,_ in selector.select(min(remaining,0.2)):
                    chunk=os.read(key.fd,65536)
                    if not chunk:
                        selector.unregister(key.fileobj);continue
                    if len(buffers[key.fileobj])+len(chunk)>max_output:
                        raise ProcessBudgetError('Subprocess output budget exceeded; raw output withheld')
                    buffers[key.fileobj].extend(chunk)
            remaining=max(0.01,deadline-time.monotonic())
            code=proc.wait(timeout=remaining)
            return subprocess.CompletedProcess(args,code,bytes(buffers[proc.stdout]),bytes(buffers[proc.stderr]))
        except BaseException:
            # Kill the local group, including helpers which inherited output pipes.
            try: os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: proc.wait(timeout=termination_grace)
            except subprocess.TimeoutExpired: pass
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
            raise
        finally:
            proc.stdout.close();proc.stderr.close()
