"""Memory process boundaries; no model, database or network calls."""
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import memory_cli


class MemoryBoundaryTests(unittest.TestCase):
    def test_memory_call_is_bounded_with_grace_and_no_automatic_wal_reset(self):
        with tempfile.TemporaryDirectory() as td:
            home=pathlib.Path(td)
            state=home/'.local/state/oracle-ai-stack';state.mkdir(parents=True)
            runtime={'bun':'/not/executed/bun','entry':'/not/executed/cli.ts','home':str(home)}
            (state/'gbrain-runtime.json').write_text(json.dumps(runtime))
            result=NS(returncode=0,stdout=b'{"facts":[],"total":0}',stderr=b'')
            output=NS(buffer=io.BytesIO())
            with (
                patch.object(memory_cli,'get_profile',return_value=NS(home=home,user='fixture')),
                patch.object(memory_cli.pwd,'getpwnam',return_value=NS(pw_uid=os.getuid())),
                patch.object(memory_cli.sys,'argv',['memory_cli.py','recall','projects/fixture']),
                patch.object(memory_cli.sys,'stdout',output),
                patch.object(memory_cli,'run_bounded',return_value=result) as bounded,
            ):
                memory_cli.main()
            bounded.assert_called_once()
            options=bounded.call_args.kwargs
            self.assertEqual(options['termination_grace'],30)
            self.assertEqual(options['max_output'],262144)
            self.assertEqual(options['env']['GBRAIN_PGLITE_WAL_REPAIR'],'off')
            self.assertEqual(json.loads(output.buffer.getvalue()),{'facts':[],'total':0})


if __name__=='__main__':
    unittest.main()
