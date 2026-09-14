"""Offline contracts/mocked cloud behavior. Not real OCI or agent acceptance."""
import base64, io, json, pathlib, sys, tempfile, time, unittest, uuid
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import stack,oci_provision as oci,profile_spec as ps,worker_bridge as bridge,profiles_runtime as pr
from stacklib import StackError,atom_json

CFG={'OCI_USER':'ocid1.user.oc1..user','OCI_TENANCY':'ocid1.tenancy.oc1..tenant',
 'OCI_FINGERPRINT':':'.join(['ab']*16),'OCI_REGION':'example-region-1','OCI_KEY_FILE':'/local/key.pem',
 'DOMAIN':'example.com','OCI_SSH_ALLOWED_CIDR':'8.8.8.8/32'}
class Models:
    def __getattr__(self,name):return lambda **kwargs:NS(**kwargs)
SDK=NS(core=NS(models=Models()),pagination=NS(list_call_get_all_results=lambda fn,*a,**kw:fn(*a,**kw)))
def response(value):return NS(data=value)
def clients():
    identity=Mock();compute=Mock();net=Mock()
    identity.list_region_subscriptions.return_value=response([NS(region_name='example-region-1',is_home_region=True)])
    identity.list_availability_domains.return_value=response([NS(name='abc:AD-1'),NS(name='abc:AD-2')])
    image=NS(id='ocid1.image.oc1..image1',operating_system='Canonical Ubuntu',operating_system_version='24.04',display_name='Canonical-Ubuntu-24.04-aarch64',lifecycle_state='AVAILABLE')
    compute.list_images.return_value=response([image]);compute.get_image.return_value=response(image)
    compute.list_shapes.return_value=response([NS(shape=oci.SHAPE)])
    compute.list_instances.return_value=response([])
    return identity,compute,net
class CloudTests(unittest.TestCase):
    def worker(self,t,cfg=None):return oci.Provisioner(cfg or CFG,pathlib.Path(t),SDK,clients=clients(),sleep=lambda _:None)
    def test_fixed_size(self):
        c=oci.normalized(CFG);self.assertEqual((c['OCI_OCPUS'],c['OCI_MEMORY_GB'],c['OCI_BOOT_VOLUME_GB']),('2','12','50'))
    def test_refuse_upsize(self):
        with self.assertRaises(StackError):oci.normalized(dict(CFG,OCI_OCPUS='4'))
    def test_require_local_api_key_path(self):
        c=dict(CFG);del c['OCI_KEY_FILE']
        with self.assertRaises(StackError):oci.normalized(c)
    def test_api_key_not_ssh_key(self):self.assertNotEqual(CFG['OCI_KEY_FILE'],oci.normalized(CFG).get('ORACLE_SSH_KEY'))
    def test_no_global_ssh(self):
        with self.assertRaises(StackError):oci.normalized(dict(CFG,OCI_SSH_ALLOWED_CIDR='0.0.0.0/0'))
    def test_no_private_ssh(self):
        with self.assertRaises(StackError):oci.normalized(dict(CFG,OCI_SSH_ALLOWED_CIDR='10.0.0.1/32'))
    def test_retry_bounded(self):
        with self.assertRaises(StackError):oci.normalized(dict(CFG,OCI_MAX_ATTEMPTS='999'))
    def test_no_implicit_region_switch(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t,dict(CFG,OCI_REGION='different-1'))
            with self.assertRaises(StackError):w.preflight()
    def test_invalid_ad(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(StackError):self.worker(t,dict(CFG,OCI_AD='other')).preflight()
    def test_retry_token_persistent(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);token=w.token('launch-a');self.assertEqual(token,self.worker(t).token('launch-a'))
    def test_expired_ambiguous_token_not_reset(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);w.state['tokens']['x']={'value':'same','created':time.time()-24*3600}
            with self.assertRaises(StackError):w.token('x')
    def test_tags_prevent_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);rows=[NS(id='one',freeform_tags=w.tags),NS(id='two',freeform_tags=w.tags)]
            with self.assertRaises(StackError):w.owned(rows)
    def test_only_owned_resource_reused(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);a=NS(id='a',freeform_tags={});b=NS(id='b',freeform_tags=w.tags)
            self.assertIs(w.owned([a,b]),b)
    def test_missing_resource_not_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);w.state['resources']['vcn']='old'
            create=Mock()
            with self.assertRaises(StackError):w.ensure_resource('vcn',lambda **kw:response([]),create,NS(),{})
            create.assert_not_called()
    def test_existing_resource_no_create(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);a=NS(id='existing',freeform_tags=w.tags);create=Mock()
            out=w.ensure_resource('vcn',lambda **kw:response([a]),create,NS(),{})
            self.assertEqual(out.id,'existing');create.assert_not_called()
    def test_cloud_init_contains_only_public_key_receipt(self):
        text=base64.b64decode(oci.cloud_init()).decode();self.assertIn('ssh_host_ed25519_key.pub',text)
        self.assertNotIn('OPENCODE_API_KEY',text);self.assertNotIn('OCI_KEY',text)
    def test_fingerprint_authenticated_block(self):
        self.assertEqual(oci.parse_fingerprint('OAS_HOSTKEY_BEGIN\n256 SHA256:AbC123 owner (ED25519)\nOAS_HOSTKEY_END'),'SHA256:AbC123')
    def test_fingerprint_without_marker_rejected(self):
        with self.assertRaises(StackError):oci.parse_fingerprint('256 SHA256:abc user (ED25519)')
    def test_ambiguous_error_redacted(self):
        e=Exception('my-api-secret');self.assertNotIn('my-api-secret',oci.safe_error(e));self.assertEqual(oci.error_kind(e),'AMBIGUOUS')
    def test_preflight_no_cloud_mutations(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);p=w.preflight();self.assertEqual(p['ocpus'],2)
            self.assertFalse(w.network.method_calls);w.compute.launch_instance.assert_not_called()
    def test_pinned_image_on_resume(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);w.state['image_id']='old-image';w.preflight()
            w.compute.get_image.assert_called_with('old-image');w.compute.list_images.assert_not_called()
    def test_ambiguous_launch_reuses_ad_token(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);p=w.preflight();w.compute.launch_instance.side_effect=TimeoutError('ambiguous')
            with self.assertRaises(StackError):w.launch(p,'subnet','ssh-ed25519 public')
            calls=w.compute.launch_instance.call_args_list
            self.assertEqual(len(calls),3);self.assertEqual(len({c.kwargs['opc_retry_token'] for c in calls}),1)
            self.assertEqual({c.args[0].availability_domain for c in calls},{'abc:AD-1'})
    def test_capacity_launch_rotates_only_ad(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);p=w.preflight();e=Exception();e.code='OutOfHostCapacity';e.status=500;e.message='Out of host capacity'
            w.compute.launch_instance.side_effect=e
            with self.assertRaises(StackError):w.launch(p,'subnet','ssh-ed25519 public')
            calls=w.compute.launch_instance.call_args_list
            self.assertEqual([x.args[0].availability_domain for x in calls],['abc:AD-1','abc:AD-2','abc:AD-1'])
            self.assertTrue(all(x.args[0].shape_config.ocpus==2 for x in calls))
    def test_accepted_launch_reconciles_next_run(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);p=w.preflight();inst=NS(id='vm',freeform_tags=w.tags,shape=oci.SHAPE,shape_config=NS(ocpus=2,memory_in_gbs=12),metadata={'ssh_authorized_keys':'ssh-ed25519 public'},image_id=p['image'])
            w.compute.launch_instance.return_value=response(inst);self.assertEqual(w.launch(p,'subnet','ssh-ed25519 public').id,'vm')
            w.compute.list_instances.return_value=response([inst]);w.launch(p,'subnet','ssh-ed25519 public')
            self.assertEqual(w.compute.launch_instance.call_count,1)
    def test_provision_handoff_chain_mocked(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);p=w.preflight()
            with patch.object(w,'prepare_ssh',return_value='ssh-ed25519 public'),patch.object(w,'make_network',return_value='subnet'),patch.object(w,'launch',return_value=NS(id='vm')),patch.object(w,'wait_running'),patch.object(w,'public_ip',return_value='8.8.4.4'),patch.object(w,'fingerprint',return_value='SHA256:abc'):
                w.state['ssh_key_path']='/local/ssh/key';out=w.provision()
            self.assertEqual(out['state'],'INSTANCE_READY');h=json.loads((pathlib.Path(t)/'oci-handoff.json').read_text())
            self.assertEqual(h['ORACLE_HOST'],'8.8.4.4');self.assertNotIn('OCI_KEY_FILE',h)
    def test_intent_change_stops_before_network(self):
        with tempfile.TemporaryDirectory() as t:
            w=self.worker(t);w.state['intent_sha256']='different'
            with patch.object(w,'prepare_ssh',return_value='pub'),patch.object(w,'make_network') as create:
                with self.assertRaises(StackError):w.provision()
                create.assert_not_called()

class ProfileTests(unittest.TestCase):
    def test_unique_os_accounts_ports_state(self):
        for field in ('user','port','home','state','workspace','unit'):
            self.assertEqual(len({getattr(p,field) for p in ps.PROFILES.values()}),3)
    def test_native_config_entries_not_retired_list(self):
        c=ps.config_for(ps.PROFILES['planning'],{'DOMAIN':'example.com'},'random')
        self.assertIn('entries',c['agents']);self.assertNotIn('list',c['agents'])
    def test_default_mixed_auth(self):
        c={'OPENCODE_API_KEY':'test'}
        self.assertEqual(ps.auth_mode(c,'operations'),'chatgpt');self.assertEqual(ps.auth_mode(c,'planning'),'opencode-go')
    def test_default_no_api_key_all_chatgpt(self):
        self.assertTrue(all(ps.auth_mode({},n)=='chatgpt' for n in ps.PROFILES))
    def test_zen_config(self):self.assertEqual(ps.auth_mode({'OPENCODE_API_KEY':'x','OPENCODE_CATALOG':'zen'},'development'),'opencode')
    def test_wrong_provider_rejected(self):
        with self.assertRaises(StackError):ps.validate_model('anthropic/claude','openai')
    def test_no_invented_model(self):
        with self.assertRaises(StackError):ps.choose_model([],'openai')
        self.assertNotIn('model',ps.config_for(ps.PROFILES['operations'],{'DOMAIN':'example.com'},'t')['agents']['defaults'])
    def test_requested_model_must_exist(self):
        with self.assertRaises(StackError):ps.choose_model([{'key':'openai/listed'}],'openai','openai/absent')
    def test_unavailable_model_skipped(self):
        self.assertEqual(ps.choose_model([{'key':'opencode-go/one','available':False},{'key':'opencode-go/two','available':True}],'opencode-go'),'opencode-go/two')
    def test_planning_tool_denies(self):
        c=ps.config_for(ps.PROFILES['planning'],{'DOMAIN':'example.com'},'t');tools=c['tools']
        self.assertFalse(set(['exec','write','edit','apply_patch']) & set(tools['allow']))
        self.assertTrue(set(['exec','write','edit','apply_patch']).issubset(tools['deny']))
    def test_embedded_runtime_preserves_tool_policy(self):
        c=ps.config_for(ps.PROFILES['planning'],{'DOMAIN':'example.com'},'t')
        self.assertEqual(c['models']['providers']['openai']['agentRuntime']['id'],'openclaw')
    def test_private_gateway_binding(self):
        for p in ps.PROFILES.values():self.assertEqual(ps.config_for(p,{'DOMAIN':'example.com'},'t')['gateway']['bind'],'loopback')
    def test_no_tokens_in_units(self):
        for p in ps.PROFILES.values():
            unit=ps.gateway_unit(p);self.assertIn('EnvironmentFile=-/etc/',unit);self.assertNotIn('OPENCODE_API_KEY=',unit)
    def test_worker_nnp(self):self.assertIn('NoNewPrivileges=true',ps.gateway_unit(ps.PROFILES['development']))
    def test_assignment_exclusive_ops(self):
        m=json.loads((ROOT/'manifests/bootstrap-sources.json').read_text())
        self.assertEqual(m['roles']['operations']['exclusive'],['gbrain','gstack'])
        self.assertNotIn('gstack',json.dumps(m['roles']['planning']))
    def test_ecc_frontmatter_is_reference_not_runtime(self):
        text=(ROOT/'templates/profiles/planning/AGENTS.md').read_text();self.assertIn('NOT',text)
        self.assertNotIn('sonnet',json.dumps(ps.config_for(ps.PROFILES['development'],{'DOMAIN':'example.com'},'t')))
    def test_cloud_credentials_not_remote_payload(self):
        cfg={'DOMAIN':'example.com','OCI_KEY_FILE':'NO','OCI_KEY_PASSPHRASE':'NO','OPENCODE_API_KEY':'model-secret'}
        with patch('stack.ssh') as ssh:
            ssh.return_value=NS(stdout=b'{}');stack.remote(cfg,'openclaw')
            payload=json.loads(ssh.call_args.args[2]);self.assertNotIn('OCI_KEY_FILE',payload);self.assertEqual(payload['OPENCODE_API_KEY'],'model-secret')
            self.assertNotIn('model-secret',ssh.call_args.args[1])
    def test_gbrain_not_npm_or_paid_autoinit(self):
        text=(ROOT/'scripts/gbrain_install.py').read_text();self.assertIn("'--no-embedding'",text);self.assertNotIn("'npm','install','gbrain'",text)
    def test_three_profile_backup_scope(self):
        text=(ROOT/'scripts/operations.py').read_text();self.assertIn('PROFILES.values()',text);self.assertIn('PGLite',text)

class BridgeTests(unittest.TestCase):
    def req(self,**kw):return dict({'task_id':str(uuid.uuid4()),'prompt':'Return a plan','action':'run'},**kw)
    def test_development_plan_required(self):
        with self.assertRaises(StackError):bridge.validate_request(self.req(),'development')
    def test_no_arbitrary_command_field(self):
        with self.assertRaises(StackError):bridge.validate_request(self.req(command='sudo reboot'),'planning')
    def test_prompt_bound(self):
        with self.assertRaises(StackError):bridge.validate_request(self.req(prompt='x'*65537),'planning')
    def test_bad_uuid(self):
        with self.assertRaises(ValueError):bridge.validate_request(self.req(task_id='../escape'),'planning')
    def test_status_without_prompt(self):
        self.assertEqual(bridge.validate_request({'task_id':str(uuid.uuid4()),'action':'status'},'development')['action'],'status')
    def fakeprofile(self,t):
        home=pathlib.Path(t);atom_json(home/'.local/state/oracle-ai-stack/model-ready.json',{'auth_probe':'PASS'})
        return NS(name='planning',home=home,binary='/not/executed/openclaw',agent='planner')
    def test_task_duplicate_not_reexecuted(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.fakeprofile(t);req=self.req();runner=Mock(return_value=NS(returncode=0,stdout=b'{"answer":"plan"}'))
            first=bridge.execute(req,p,runner);second=bridge.execute(req,p,runner)
            self.assertEqual(first,second);self.assertEqual(runner.call_count,1)
    def test_task_id_input_conflict(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.fakeprofile(t);req=self.req();runner=Mock(return_value=NS(returncode=0,stdout=b'{}'));bridge.execute(req,p,runner)
            with self.assertRaises(StackError):bridge.execute(dict(req,prompt='different'),p,runner)
    def test_ambiguous_worker_never_rerun(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.fakeprofile(t);req=self.req();runner=Mock(side_effect=TimeoutError())
            first=bridge.execute(req,p,runner);bridge.execute(req,p,runner)
            self.assertEqual(first['state'],'UNCERTAIN_CHECK_TRANSCRIPT');self.assertEqual(runner.call_count,1)
    def test_model_gate(self):
        with tempfile.TemporaryDirectory() as t:
            p=NS(name='planning',home=pathlib.Path(t),agent='planner',binary='none');runner=Mock()
            self.assertEqual(bridge.execute(self.req(),p,runner)['state'],'PENDING_PROFILE_MODEL_AUTH');runner.assert_not_called()
    def test_worker_no_local_double_state_owner(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.fakeprofile(t);runner=Mock(return_value=NS(returncode=0,stdout=b'{}'));bridge.execute(self.req(),p,runner)
            self.assertNotIn('--local',runner.call_args.args[0]);self.assertIn('--profile',runner.call_args.args[0])
class FinalRegressionTests(unittest.TestCase):
    def test_recorded_instance_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as t:
            w=oci.Provisioner(CFG,pathlib.Path(t),SDK,clients=clients(),sleep=lambda _:None)
            w.state['instance_id']='original'
            with self.assertRaises(StackError):w.verify_instance(NS(id='different'),{'image':'i'},'subnet','pub')
    def test_empty_oci_optional_values_get_defaults(self):
        c=oci.normalized(dict(CFG,OCI_COMPARTMENT='',OCI_AD='',OCI_IMAGE='',OCI_SUBNET='',OCI_CREATE_NETWORK=''))
        self.assertEqual(c['OCI_COMPARTMENT'],CFG['OCI_TENANCY'])
        self.assertEqual(c['OCI_CREATE_NETWORK'],'true')
    def test_pending_receipt_revokes_previous_pass(self):
        with tempfile.TemporaryDirectory() as t:
            p=NS(name='planning',user='unused',home=pathlib.Path(t)/'home')
            with patch.object(pr,'STATE',pathlib.Path(t)/'state'),patch.object(pr,'write') as write,patch.object(pr,'own'):
                pr.invalidate_model(p)
            self.assertEqual(json.loads(write.call_args.args[1])['auth_probe'],'PENDING')
    def test_failed_catalog_does_not_leave_ready(self):
        from contextlib import nullcontext
        p=ps.PROFILES['planning']
        with patch.object(pr,'exclusive_profile_state',return_value=nullcontext()),patch.object(pr,'invalidate_model') as invalidate,patch.object(pr,'oc',side_effect=StackError('catalog unavailable')):
            with self.assertRaises(StackError):pr.configure_one(p,{'provider':'opencode-go','requested_model':''})
            invalidate.assert_called_once_with(p,'MODEL_PROBE_PENDING')
    def test_model_probe_does_not_restart_before_maintenance(self):
        import inspect
        source=inspect.getsource(pr.configure_one)
        self.assertLess(source.index('with exclusive_profile_state'),source.index("'config','set'"))
        self.assertNotIn("'restart'",source)
    def test_oauth_revokes_probe_receipt(self):
        self.assertIn('OAUTH_REAUTHENTICATION_PENDING',(ROOT/'scripts/profile_admin.py').read_text())

if __name__=='__main__':unittest.main()
