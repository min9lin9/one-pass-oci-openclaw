import contextlib, importlib, inspect, json, os, pathlib, subprocess, sys, tarfile, tempfile, unittest, uuid
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import fssecure, evidence, stack, stacklib, profiles_runtime as pr, profile_spec as ps, worker_bridge as bridge, operations, oci_provision, target_preflight
from process_guard import run_bounded, ProcessBudgetError

class FileSafetyTests(unittest.TestCase):
    def test_regular_atomic_write(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'new/secret';fssecure.write_text(p,'first');fssecure.write_text(p,'second')
            self.assertEqual(p.read_text(),'second');self.assertEqual(p.stat().st_mode & 0o777,0o600)
    def test_predictable_temp_symlinks_no_longer_followed(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);target=d/'config';outside=d/'outside';outside.write_text('safe')
            for suffix in ('tmp','new'):(d/('.config.'+suffix)).symlink_to(outside)
            fssecure.write_text(target,'value')
            self.assertEqual(outside.read_text(),'safe');self.assertEqual(target.read_text(),'value')
    def test_target_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);o=d/'out';o.write_text('safe');(d/'target').symlink_to(o)
            with self.assertRaises(fssecure.FileSafetyError):fssecure.write_text(d/'target','bad')
            self.assertEqual(o.read_text(),'safe')
    def test_parent_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);(d/'real').mkdir();(d/'link').symlink_to(d/'real',target_is_directory=True)
            with self.assertRaises(fssecure.FileSafetyError):fssecure.write_text(d/'link/secret','bad')
            self.assertFalse((d/'real/secret').exists())
    def test_hardlinked_target_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);p=d/'one';p.write_text('safe');os.link(p,d/'two')
            with self.assertRaises(fssecure.FileSafetyError):fssecure.write_text(p,'bad')
            self.assertEqual(p.read_text(),'safe')
    def test_fifo_target_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'pipe';os.mkfifo(p)
            with self.assertRaises(fssecure.FileSafetyError):fssecure.write_text(p,'bad')
    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(fssecure.FileSafetyError):fssecure.write_text(pathlib.Path(td)/'x/../bad','bad')
    def test_atom_json_rejects_link(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);p=d/'out';p.write_text('safe');(d/'link').symlink_to(p)
            with self.assertRaises(stacklib.StackError):stacklib.atom_json(d/'link',{'bad':True})
    def test_mode_change_invalidates_tree_seal(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td);p=d/'script';p.write_text('data');p.chmod(0o644);a=stacklib.digest_tree(d);p.chmod(0o755)
            self.assertNotEqual(a,stacklib.digest_tree(d))
    def test_profile_writer_no_fixed_temporary_name(self):
        source=inspect.getsource(pr.write);self.assertIn('write_text',source);self.assertNotIn('.tmp',source)

class EvidenceTests(unittest.TestCase):
    def test_canonical_marker(self):self.assertTrue(evidence.exact_marker({'payloads':[{'text':'test'}]},'test'))
    def test_nested_marker(self):self.assertTrue(evidence.exact_marker({'status':'ok','result':{'payloads':[{'text':'test'}]}},'test'))
    def test_echo_in_metadata_not_success(self):self.assertFalse(evidence.exact_marker({'payloads':[{'text':'no'}],'prompt':'test'},'test'))
    def test_echo_in_error_not_success(self):self.assertFalse(evidence.exact_marker({'error':'test','payloads':[{'text':'test'}]},'test'))
    def test_rc_zero_not_enough(self):self.assertFalse(evidence.successful_response({'ok':False,'error':'failure'},0))
    def test_pending_not_success(self):self.assertFalse(evidence.successful_response({'status':'in_flight','payloads':[{'text':'test'}]}))
    def test_unknown_schema_not_success(self):self.assertFalse(evidence.successful_response({'answer':'test'}))
    def test_nonzero_code_fails(self):self.assertFalse(evidence.exact_marker({'payloads':[{'text':'test'}]},'test',1))
    def test_meta_error_fails(self):self.assertFalse(evidence.successful_response({'payloads':[{'text':'x'}],'meta':{'error':{'message':'failed'}}}))
    def test_payload_error_fails(self):self.assertFalse(evidence.successful_response({'payloads':[{'text':'x','isError':True}]}))
    def test_marker_substring_not_enough(self):self.assertFalse(evidence.exact_marker({'payloads':[{'text':'prefix test suffix'}]},'test'))
    def test_model_identity_must_match(self):
        r={'payloads':[{'text':'x'}],'meta':{'agentMeta':{'provider':'openai','model':'abc'}}}
        self.assertTrue(evidence.selected_model_observed(r,'openai','openai/abc'));self.assertFalse(evidence.selected_model_observed(r,'opencode-go','opencode-go/abc'))
    def test_missing_model_identity_fails(self):self.assertFalse(evidence.selected_model_observed({'payloads':[{'text':'x'}]},'openai','openai/a'))
    def test_failed_receipt_not_observed(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'e.json';p.write_text(json.dumps({'state':'DELEGATION_INCOMPLETE','profiles':{}}))
            self.assertEqual(evidence.delegation_receipt(p),'FAILED_OR_INCOMPLETE')
    def test_success_receipt_needs_both_profiles(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'e.json';p.write_text(json.dumps({'state':'DELEGATION_MARKERS_PASSED','profiles':{'planning':{'marker_roundtrip':'PASS'}}}))
            self.assertEqual(evidence.delegation_receipt(p),'FAILED_OR_INCOMPLETE')
    def test_success_receipt_not_full_e2e(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'e.json';p.write_text(json.dumps({'state':'DELEGATION_MARKERS_PASSED','profiles':{x:{'marker_roundtrip':'PASS'} for x in ('planning','development')}}))
            self.assertIn('NOT_FULL_TASK_E2E',evidence.delegation_receipt(p))

class ProcessTests(unittest.TestCase):
    def test_output_capture(self):
        r=run_bounded([sys.executable,'-c','import sys;print(sys.stdin.read())'],input=b'hello',timeout=3)
        self.assertEqual(r.stdout,b'hello\n');self.assertEqual(r.returncode,0)
    def test_stdout_budget(self):
        with self.assertRaises(ProcessBudgetError):run_bounded([sys.executable,'-c','print("a"*100000)'],max_output=500,timeout=3)
    def test_stderr_budget(self):
        with self.assertRaises(ProcessBudgetError):run_bounded([sys.executable,'-c','import sys;sys.stderr.write("a"*100000)'],max_output=500,timeout=3)
    def test_timeout(self):
        with self.assertRaises(ProcessBudgetError):run_bounded([sys.executable,'-c','import time;time.sleep(10)'],timeout=0.1)
    def test_budget_error_does_not_print_secret(self):
        with self.assertRaises(ProcessBudgetError) as ctx:run_bounded([sys.executable,'-c','print("MY_FAKE_SECRET"*10000)'],max_output=50,timeout=3)
        self.assertNotIn('MY_FAKE_SECRET',str(ctx.exception))

class WorkflowTests(unittest.TestCase):
    def test_review_notes_excluded_from_upload(self):self.assertIsNone(stack.tar_filter(tarfile.TarInfo('stage/review-notes.md')))
    def test_upload_preflight_before_archive_mutations(self):
        with patch.object(stack,'verify_all'),patch.object(stack,'ssh',side_effect=stacklib.StackError('read-only preflight failed')) as call:
            with self.assertRaises(stacklib.StackError):stack.upload({'DOMAIN':'example.com'},pathlib.Path('/not-used'))
            self.assertEqual(call.call_count,1);self.assertIn('validate',call.call_args.args[1])
    def test_catalog_supported_flags(self):
        source=inspect.getsource(pr.configure_one)
        self.assertIn("'models','refresh','--json'",source)
        self.assertIn("'models','list','--all','--provider'",source)
        self.assertNotIn("'list','--agent'",source);self.assertNotIn("'--refresh'",source)
    def test_actual_inference_required(self):
        source=inspect.getsource(pr.configure_one)
        self.assertIn('exact_marker',source);self.assertIn('selected_model_observed',source)
    def test_oauth_targets_agent_store(self):
        text=(ROOT/'scripts/profile_admin.py').read_text();self.assertIn("'auth','--agent',spec.agent,'login'",text)
    def test_all_root_entrypoints_share_lock(self):
        for name in ('remote.py','profile_admin.py','gstack_full.py','operations.py'):
            with self.subTest(name=name):self.assertIn('with locked():',(ROOT/'scripts'/name).read_text())
    def test_existing_backup_cannot_get_new_password(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);state=root/'state';state.mkdir();(state/'managed.json').write_text('{}');repo=root/'repo';repo.mkdir();(repo/'config').write_text('exists')
            with patch.object(operations,'STATE',state),patch.object(operations,'REPO',repo),patch.object(operations,'PASSWORD',root/'password'),patch.object(operations,'write') as writer:
                with self.assertRaises(stacklib.StackError):operations.initialize()
                writer.assert_not_called()
    def test_backup_resume_error_is_not_just_printed(self):
        source=inspect.getsource(operations.backup)
        self.assertIn("if errors: raise StackError",source);self.assertIn('backup-resume.json',source)
    def test_dns_private_exception_is_destination_specific(self):
        source=(ROOT/'scripts/fetch_egress.sh').read_text()
        self.assertIn('-d "$resolver" -p udp --dport 53',source)
        self.assertNotIn('"$chain" -p udp --dport 53',source)
    def test_egress_policy_built_before_attaching(self):
        source=(ROOT/'scripts/fetch_egress.sh').read_text()
        self.assertLess(source.index('-A "$chain" -j RETURN'),source.index('-I OUTPUT 1'))
        self.assertNotIn('-F "$chain"',source)
    def test_worker_error_response_preserved_no_retry(self):
        with tempfile.TemporaryDirectory() as td:
            home=pathlib.Path(td);stacklib.atom_json(home/'.local/state/oracle-ai-stack/model-ready.json',{'auth_probe':'PASS'})
            p=NS(name='planning',home=home,binary='none',agent='planner')
            req={'task_id':str(uuid.uuid4()),'prompt':'x'};r=Mock(return_value=NS(returncode=0,stdout=b'{"ok":false,"error":"x"}'))
            out=bridge.execute(req,p,r);self.assertEqual(out['state'],'FAILED_OR_UNCERTAIN')
            bridge.execute(req,p,r);self.assertEqual(r.call_count,1)
    def test_oci_network_waits_before_use(self):
        p=object.__new__(oci_provision.Provisioner);p.sleep=Mock();p.network=NS(get_vcn=Mock(side_effect=[NS(data=NS(id='v',lifecycle_state='PROVISIONING')),NS(data=NS(id='v',lifecycle_state='AVAILABLE'))]))
        self.assertEqual(p.network_ready('vcn',NS(id='v')).id,'v');p.sleep.assert_called_once_with(5)
    def test_oci_unknown_network_state_stops(self):
        p=object.__new__(oci_provision.Provisioner);p.sleep=Mock();p.network=NS(get_vcn=Mock(return_value=NS(data=NS(id='v',lifecycle_state='UNKNOWN'))))
        with self.assertRaises(stacklib.StackError):p.network_ready('vcn',NS(id='v'))
    def test_preflight_refuses_unmanaged_account(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError):target_preflight.validate({'domain':'example.com'},pathlib.Path(td)/'base',pathlib.Path(td)/'state',account_lookup=Mock(return_value=NS()))
    def test_preflight_refuses_unmanaged_files(self):
        with tempfile.TemporaryDirectory() as td:
            base=pathlib.Path(td)/'base';base.mkdir();(base/'unrelated').write_text('keep')
            with self.assertRaises(RuntimeError):target_preflight.validate({'domain':'example.com'},base,pathlib.Path(td)/'state',account_lookup=Mock(side_effect=KeyError()))
            self.assertEqual((base/'unrelated').read_text(),'keep')


class DistributionTests(unittest.TestCase):
    def fixture(self,root):
        import package_manifest as pm
        (root/'README.md').write_text('reviewed source');(root/pm.MANIFEST).write_text(json.dumps(pm.build(root)))
    def test_default_publish_is_offline_plan(self):
        import publish
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);self.fixture(root)
            with patch.object(publish,'command') as command:
                result=publish.run(root);command.assert_not_called()
            self.assertEqual(result['visibility'],'private');self.assertFalse(result['mutation'])
    def test_publish_refuses_modified_package(self):
        import publish,package_manifest as pm
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);self.fixture(root);(root/'README.md').write_text('changed')
            with self.assertRaises(pm.PackageError):publish.run(root)
    def test_runtime_state_not_selected(self):
        import package_manifest as pm
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);self.fixture(root);(root/'secrets.env').write_text('private');(root/'state').mkdir();(root/'state/auth.json').write_text('private')
            self.assertEqual([n for n,_,_ in pm.selected(root)],['README.md'])
    def test_unknown_private_key_stops_publish(self):
        import package_manifest as pm
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);(root/'README.md').write_text('-----BEGIN '+'PRIVATE KEY-----')
            with self.assertRaises(pm.PackageError):pm.build(root)
    def test_install_preserves_existing_skill(self):
        import install_skill
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)/'source';root.mkdir();self.fixture(root);home=pathlib.Path(td)/'home'
            dest=install_skill.install(root,home);(dest/'README.md').write_text('user edit')
            with self.assertRaises(RuntimeError):install_skill.install(root,home)
            self.assertEqual((dest/'README.md').read_text(),'user edit')
    def test_publish_uses_exact_requested_spelling(self):
        import publish
        self.assertEqual(publish.REPO,'min9lin9/one-pass-oci-openclaw')
    def test_publish_no_force_push(self):
        import publish
        self.assertNotIn("'--force'",inspect.getsource(publish));self.assertNotIn("'--force-with-lease'",inspect.getsource(publish))
    def test_agent_directory_copy_does_not_run_privileged(self):
        source=(ROOT/'scripts/gbrain_install.py').read_text()
        self.assertIn("as_user(p,['/usr/bin/python3'",source)
        self.assertNotIn('shutil.copytree(src,dest)',source)

class BackupRecoveryTests(unittest.TestCase):
    def test_backup_volume_inventory_requires_only_proxy_volumes(self):
        with tempfile.TemporaryDirectory() as td:
            base=pathlib.Path(td)
            (base/'compose.proxy.json').write_text(json.dumps({'volumes':{
                'data':{'name':'oracle-proxy-data'},'config':{'name':'oracle-proxy-config'}}}))
            def inspect(args,**kwargs):
                name=args[-1]
                row=[{'Mountpoint':'/var/lib/docker/volumes/'+name+'/_data'}]
                return NS(returncode=0,stdout=json.dumps(row).encode())
            with patch.object(operations,'BASE',base),patch.object(operations,'run',side_effect=inspect):
                mounts=operations.own_volumes()
            self.assertEqual(set(mounts),{'oracle-proxy-data','oracle-proxy-config'})

    def test_container_inventory_is_limited_to_proxy_project(self):
        with patch.object(operations,'run',return_value=NS(returncode=0,stdout=b'abcdef123456\n')) as run:
            self.assertEqual(operations.running_containers(),['abcdef123456'])
        run.assert_called_once_with(['docker','ps','-q','--filter','label=com.docker.compose.project=oracle-proxy'])

    def test_uninstall_stops_only_owned_openclaw_and_proxy_services(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);state=root/'state';base=root/'base';state.mkdir();base.mkdir()
            (state/'managed.json').write_text('{"domain":"example.com"}')
            (base/'compose.proxy.json').write_text('{}')
            calls=[]
            def command(args,**kwargs):
                calls.append(args)
                return NS(returncode=0,stdout=b'')
            with patch.object(operations,'STATE',state),patch.object(operations,'BASE',base), \
                 patch.object(operations,'run',side_effect=command):
                operations.uninstall('uninstall:example.com')
            docker=[args for args in calls if args and args[0]=='docker']
            self.assertEqual(docker,[['docker','compose','-f',str(base/'compose.proxy.json'),'down']])

    def test_resume_failure_returns_error_even_after_snapshot_success(self):
        with tempfile.TemporaryDirectory() as td:
            state=pathlib.Path(td).resolve();(state/'managed.json').write_text('{"domain":"example.com"}')
            def command(args,**kwargs):
                if args[:2]==['docker','start']:return NS(returncode=1,stdout=b'')
                return NS(returncode=0,stdout=b'')
            def restic(*args,**kwargs):
                return NS(returncode=0,stdout=b'{"message_type":"summary","snapshot_id":"abcdef12"}\n')
            real_exists=pathlib.Path.exists
            def fixture_exists(path):
                # This unit test owns only its temporary state tree. Do not stat
                # /etc/sudoers.d or other deployment paths on an unprivileged CI host.
                return real_exists(path) if path.is_relative_to(state) else False
            with (
                tempfile.TemporaryFile(mode='w+') as guard,
                patch.object(operations,'STATE',state),
                patch.object(operations,'initialize'),
                patch.object(operations,'own_volumes',return_value={}),
                patch.object(operations,'running_containers',return_value=['abc123']),
                patch.object(operations,'run',side_effect=command),
                patch.object(operations,'restic',side_effect=restic),
                patch.object(operations,'open',return_value=guard,create=True),
                patch.object(pathlib.Path,'exists',autospec=True,side_effect=fixture_exists),
            ):
                with self.assertRaises(stacklib.StackError):operations.backup()
            receipt=json.loads((state/'backup-resume.json').read_text())
            self.assertEqual(receipt['state'],'FAIL');self.assertEqual(receipt['snapshot'],'abcdef12')
            self.assertIn('containers',receipt['components_not_resumed'])

if __name__=='__main__':unittest.main()
