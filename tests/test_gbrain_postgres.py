"""Offline contracts for the approved private GBrain PostgreSQL deployment."""
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import gbrain_install
import operations
from stacklib import StackError,digest_tree


class GBrainPostgresComposeTests(unittest.TestCase):
    def test_database_is_private_persistent_and_uses_file_secret(self):
        # Given: the published deployment template is the real deployment input.
        path=ROOT/'templates/gbrain-postgres.compose.json'
        # When: its machine-consumed configuration is loaded.
        compose=json.loads(path.read_text())
        database=compose['services']['postgres']
        # Then: no public listener, inline password, or retired Buzz volume is used.
        self.assertEqual(database['ports'],['127.0.0.1:5434:5432'])
        self.assertEqual(database['restart'],'unless-stopped')
        self.assertIn('@sha256:',database['image'])
        self.assertNotIn('POSTGRES_PASSWORD',database['environment'])
        self.assertEqual(database['environment']['POSTGRES_PASSWORD_FILE'],
                         '/run/secrets/gbrain_admin_password')
        self.assertEqual(compose['volumes']['data']['name'],'oracle-gbrain-data')
        self.assertIn('data:/var/lib/postgresql/data',database['volumes'])
        self.assertEqual(database['stop_grace_period'],'90s')


class GBrainPostgresPreservationTests(unittest.TestCase):
    def test_backup_refuses_to_claim_protection_for_unmanaged_postgres(self):
        # Given: GBrain points at an external database with no reviewed backup path.
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td).resolve();state=root/'state';state.mkdir()
            (state/'managed.json').write_text('{"domain":"example.com"}')
            profile=NS(home=root/'home',state=root/'home/state',unit='oracle-openclaw-operations.service')
            brain=profile.state/'gbrain/.gbrain';brain.mkdir(parents=True)
            (brain/'config.json').write_text(json.dumps(
                {'engine':'postgres','database_url':'postgresql://fixture@db.example/gbrain'}))
            real_exists=pathlib.Path.exists
            def fixture_exists(path):
                return path.is_relative_to(root) and real_exists(path)
            with (
                tempfile.TemporaryFile(mode='w+') as guard,
                patch.object(operations,'STATE',state),
                patch.object(operations,'PROFILES',{'operations':profile}),
                patch.object(operations,'initialize'),
                patch.object(operations,'own_volumes',return_value={}),
                patch.object(operations,'running_containers',return_value=[]),
                patch.object(operations,'run',return_value=NS(returncode=0,stdout=b'')),
                patch.object(operations,'restic',return_value=NS(
                    returncode=0,stdout=b'{"message_type":"summary","snapshot_id":"abcdef12"}\n')) as restic,
                patch.object(operations,'open',return_value=guard,create=True),
                patch.object(pathlib.Path,'exists',autospec=True,side_effect=fixture_exists),
            ):
                # When/then: file backup must fail closed before claiming remote DB coverage.
                with self.assertRaises(StackError):
                    operations.backup()
                restic.assert_not_called()

    def test_reinstall_preserves_existing_postgres_memory_configuration(self):
        # Given: the reviewed runtime is installed and already uses private Postgres.
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            home=root/'home';state=root/'state';state.mkdir()
            profile=NS(home=home,state=home/'.openclaw-operations',prefix=home/'prefix',user='fixture')
            stage=root/'stage';source=stage/'aux/gbrain';source.mkdir(parents=True)
            (source/'README.md').write_text('fixture')
            base=home/'.local/share/oracle-ai-stack'
            bun=base/'bun/bin/bun';bun.parent.mkdir(parents=True);bun.touch()
            commit='a'*40
            installed=base/'gbrain-source'/commit;installed.mkdir(parents=True)
            (installed/'.oas-install-complete').write_text(commit)
            brain=profile.state/'gbrain/.gbrain';brain.mkdir(parents=True)
            config=brain/'config.json'
            original=json.dumps({'engine':'postgres','embedding_disabled':True,
                                 'database_url':'postgresql://fixture@127.0.0.1:5434/gbrain'})
            config.write_text(original)
            lock={'aux_sources':{'gbrain':{'commit':commit,'sha256':digest_tree(source)}}}
            with (
                patch.object(gbrain_install,'os',NS(geteuid=lambda:0)),
                patch.object(gbrain_install,'get_profile',return_value=profile),
                patch.object(gbrain_install,'STATE',state),
                patch.object(gbrain_install,'own'),
                patch.object(gbrain_install,'as_user',return_value=NS(stdout=b'1.3.11\n')) as run,
            ):
                # When: the existing managed installation is reconciled.
                result=gbrain_install.install(stage,lock)
            # Then: the selected engine survives, with no reinitialization.
            self.assertEqual(config.read_text(),original)
            self.assertEqual(result['engine'],'postgres')
            commands=[list(map(str,call.args[1])) for call in run.call_args_list]
            self.assertEqual(len(commands),3)
            self.assertEqual(commands[-1][-3:],['engine','status','--json'])
            self.assertFalse(any('--pglite' in command for command in commands))


if __name__=='__main__':
    unittest.main()
