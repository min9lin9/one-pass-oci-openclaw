#!/usr/bin/env python3
"""Install this verified package into the local Codex user skill directory.
Refuses an existing target: preserve it and review a deliberate upgrade instead.
"""
import pathlib,shutil,sys,tempfile
from package_manifest import verify,selected,MANIFEST
NAME='one-pass-oci-openclaw'

def install(root,home=None):
    verify(root);home=pathlib.Path(home or pathlib.Path.home());parent=home/'.agents/skills';target=parent/NAME
    parent.mkdir(parents=True,exist_ok=True)
    if target.exists() or target.is_symlink():raise RuntimeError('Skill already exists; preserve existing edits and perform a reviewed replacement')
    with tempfile.TemporaryDirectory(prefix='.one-pass-',dir=parent) as td:
        stage=pathlib.Path(td)/NAME;stage.mkdir()
        for name,blob,mode in selected(root):
            p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob);p.chmod(0o755 if mode else 0o644)
        (stage/MANIFEST).write_bytes((pathlib.Path(root)/MANIFEST).read_bytes());verify(stage)
        stage.rename(target)
    return target
if __name__=='__main__':
    try:print(install(pathlib.Path(__file__).resolve().parents[1]))
    except Exception as e:print('INSTALL_BLOCKED: '+str(e),file=sys.stderr);sys.exit(2)
