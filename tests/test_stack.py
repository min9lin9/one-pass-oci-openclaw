import io, json, os, pathlib, sys, tarfile, tempfile, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import extensions, stack, stacklib, public_read, document_read, remote, profiles_runtime
from stacklib import StackError

class ValidationTests(unittest.TestCase):
    def test_domain_plain(self): self.assertEqual(stacklib.domain_name('Example.COM.'),'example.com')
    def test_domain_reject_url(self):
        with self.assertRaises(StackError): stacklib.domain_name('https://example.com')
    def test_domain_reject_injection(self):
        with self.assertRaises(StackError): stacklib.domain_name('x.com;reboot')
    def test_domain_reject_ip(self):
        with self.assertRaises(StackError): stacklib.domain_name('127.0.0.1')
    def test_tailnet_range(self): self.assertEqual(stacklib.tailnet_ipv4('100.64.1.2'),'100.64.1.2')
    def test_tailnet_not_all_100(self):
        with self.assertRaises(StackError): stacklib.tailnet_ipv4('100.1.1.1')
    def test_repo_traversal(self):
        with self.assertRaises(StackError): stacklib.repo_name('../repo')
    def test_env_no_execution(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'secrets.env'; p.write_text('TOKEN="$(touch /tmp/never-run)"\nDOMAIN=example.com\n'); p.chmod(0o600)
            self.assertEqual(stacklib.load_env(p)['TOKEN'],'$(touch /tmp/never-run)')
    def test_env_reject_permissions(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'s'; p.write_text('TOKEN=x'); p.chmod(0o644)
            with self.assertRaises(StackError): stacklib.load_env(p)
    def test_env_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'s'; p.write_text('TOKEN=a\nTOKEN=b');p.chmod(0o600)
            with self.assertRaises(StackError): stacklib.load_env(p)
    def test_env_custom_ssh(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'s';p.write_text('SSH_PORT=2222\n');p.chmod(0o600)
            self.assertEqual(stacklib.load_env(p)['SSH_PORT'],'2222')

class SourceTests(unittest.TestCase):
    def archive(self,name,typ=None):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w') as tf:
            m=tarfile.TarInfo(name)
            if typ: m.type=typ;m.linkname='/etc/passwd'
            else: m.size=2
            tf.addfile(m,None if typ else io.BytesIO(b'ok'))
        return buf.getvalue()
    def test_archive_regular(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t);extensions.safe_extract(self.archive('dir/a.txt'),p)
            self.assertEqual((p/'dir/a.txt').read_text(),'ok')
    def test_archive_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(StackError):extensions.safe_extract(self.archive('../escape'),pathlib.Path(t))
    def test_archive_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(StackError):extensions.safe_extract(self.archive('link',tarfile.SYMTYPE),pathlib.Path(t))
    def test_tree_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t);(p/'l').symlink_to('/etc/passwd')
            with self.assertRaises(StackError):stacklib.digest_tree(p)
    def test_skill_name(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'SKILL.md';p.write_text('---\nname: sample-skill\ndescription: local\n---\nText')
            self.assertEqual(extensions.parse_name(p),'sample-skill')
    def test_missing_description(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'SKILL.md';p.write_text('---\nname: sample\n---')
            with self.assertRaises(StackError):extensions.parse_name(p)
    def test_install_preserves_user_edits(self):
        with tempfile.TemporaryDirectory() as t:
            t=pathlib.Path(t);src=t/'src';dst=t/'skills';src.mkdir();dst.mkdir()
            (src/'SKILL.md').write_text('---\nname: sample\ndescription: test\n---\nA')
            receipt=extensions.install_one(src,dst,{'commit':'a'*40},{})
            (dst/'sample/SKILL.md').write_text('user edit')
            with self.assertRaises(StackError):extensions.install_one(src,dst,{'commit':'b'*40},{'sample':receipt})
    def test_install_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            t=pathlib.Path(t);src=t/'src';dst=t/'skills';src.mkdir();dst.mkdir()
            (src/'SKILL.md').write_text('---\nname: sample\ndescription: test\n---\nA')
            r=extensions.install_one(src,dst,{'commit':'a'*40},{})
            second=extensions.install_one(src,dst,{'commit':'a'*40},{'sample':r})
            self.assertEqual(r['installed_sha256'],second['installed_sha256'])

class OpenClawOnlyWorkflowTests(unittest.TestCase):
    def test_prepare_has_no_buzz_source_or_plugin(self):
        captured={}
        package={'version':'1.2.3','integrity':'sha512-fixture'}
        with patch.object(stack,'stage_extensions'), \
             patch.object(stack,'snapshot',return_value='a'*40) as snapshot, \
             patch.object(stack,'download',return_value='b'*64), \
             patch.object(stack,'digest_tree',return_value='c'*64), \
             patch.object(stack,'get_json',return_value={'info':{'version':'1.2.3'}}), \
             patch.object(stack,'npm_version',return_value=package) as npm, \
             patch.object(stack,'atom_json',side_effect=lambda path,value:captured.update(value)):
            stack.prepare(pathlib.Path('/fixture/stage'))
        self.assertNotIn('block/buzz',[call.args[0] for call in snapshot.call_args_list])
        self.assertNotIn('@openclaw/buzz',[call.args[0] for call in npm.call_args_list])
        self.assertFalse(any(key.startswith('buzz_') for key in captured))

    def test_setup_runs_only_openclaw_components(self):
        cfg={'DOMAIN':'example.com','CLOUDFLARE_API_TOKEN':'test-secret-not-real',
             'ORACLE_HOST':'192.0.2.1'}
        with tempfile.TemporaryDirectory() as td, \
             patch.object(stack,'verify_all'), \
             patch.object(stack,'cloudflare_zone',return_value='zone'), \
             patch.object(stack,'ssh'), \
             patch.object(stack,'upload'), \
             patch.object(stack,'dns_plan',return_value=[]), \
             patch.object(stack,'atom_json'), \
             patch.object(stack,'star_prompt_repo'), \
             patch.object(stack,'remote',side_effect=lambda _cfg,action,*args,**kwargs:
                          {'tailscale_ip':'100.64.1.1'} if action=='host' else
                          ({'overall':'READY'} if action=='status' else {'phase':action})) as remote:
            stack.setup(cfg,pathlib.Path(td)/'stage',pathlib.Path(td)/'state')
        actions=[call.args[1] for call in remote.call_args_list]
        self.assertEqual(actions,['host','openclaw','proxy','extensions','gbrain','status'])

    def test_proxy_routes_only_openclaw(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);base=root/'base';state=root/'state';etc=root/'etc'
            base.mkdir();state.mkdir();etc.mkdir()
            (state/'network.json').write_text('{"tailscale_ip":"100.64.1.1"}')
            lock={'caddy_dns_commit':'a'*40}
            (state/'caddy-build-lock.json').write_text(json.dumps({
                'cloudflare_commit':lock['caddy_dns_commit'],
                'parents':{'caddy:2-builder':'builder@sha256:x','caddy:2-alpine':'caddy@sha256:y'},
                'caddy_version':'v2.10.0'}))
            with patch.object(remote,'BASE',base),patch.object(remote,'STATE',state), \
                 patch.object(remote,'ETC',etc),patch.object(remote,'write') as write, \
                 patch.object(remote,'atom_json'), \
                 patch.object(remote,'run',return_value=__import__('subprocess').CompletedProcess([],0,b'',b'')) as run:
                remote.proxy_install({},lock)
            caddy=next(call.args[1] for call in write.call_args_list if pathlib.Path(call.args[0]).name=='Caddyfile')
            compose=run.call_args_list[-1].args[0]
            self.assertIn('--force-recreate',compose)
            self.assertIn('https://openclaw.{$DOMAIN}',caddy)
            self.assertNotIn('buzz.',caddy.lower())
            self.assertIn('bind {$TAILSCALE_IP}',caddy)

    def test_status_reports_services_without_claiming_client_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);base=root/'base';state=root/'state';home=root/'home'
            base.mkdir();state.mkdir();(home/'.local/state/oracle-ai-stack').mkdir(parents=True)
            (base/'compose.proxy.json').write_text('{}')
            (home/'.local/state/oracle-ai-stack/runtime-checks.json').write_text('{}')
            (state/'gbrain-install.json').write_text('{}')
            profiles={name:{'gateway':'PASS','auth':'NOT_PROBED'} for name in ('operations','planning','development')}
            def command(args,**kwargs):
                stdout=b'proxy\n' if args[:4]==['docker','compose','-f',str(base/'compose.proxy.json')] else b''
                return __import__('subprocess').CompletedProcess(args,0,stdout,b'')
            with patch.object(remote,'BASE',base),patch.object(remote,'STATE',state),patch.object(remote,'HOME',home), \
                 patch.object(remote,'run',side_effect=command) as run, \
                 patch.object(profiles_runtime,'profile_status',return_value=profiles):
                result=remote.status()
            self.assertEqual(result['overall'],'SERVICES_RUNNING')
            self.assertEqual(result['client_verification'],'NOT_TESTED')
            self.assertFalse(any('buzz' in key.lower() for key in result['checks']))
            self.assertFalse(any('oracle-buzz' in str(call.args) for call in run.call_args_list))


class NetworkTests(unittest.TestCase):
    cfg={'DOMAIN':'example.com','CLOUDFLARE_API_TOKEN':'test-secret-not-real'}
    def test_dns_no_public_proxy(self):
        with patch('stack.cf_request',return_value={'result':[]}):
            actions=stack.dns_plan(self.cfg,'zone','100.64.1.1')
            self.assertEqual(len(actions),1)
            self.assertEqual(actions[0][2]['name'],'openclaw.example.com')
            self.assertFalse(actions[0][2]['proxied'])
    def test_dns_does_not_overwrite_unmanaged(self):
        with patch('stack.cf_request',return_value={'result':[{'type':'A','content':'192.0.2.1','id':'x'}]}):
            with self.assertRaises(StackError):stack.dns_plan(self.cfg,'zone','100.64.1.1')
    def test_dns_conflict_aaaa(self):
        with patch('stack.cf_request',return_value={'result':[{'type':'AAAA','content':'::1','id':'x'}]}):
            with self.assertRaises(StackError):stack.dns_plan(self.cfg,'zone','100.64.1.1')
    def test_reader_loopback_rejected(self):
        with patch('public_read.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError):public_read.validate_url('https://example.com')
    def test_reader_metadata_rejected(self):
        with patch('public_read.socket.getaddrinfo',return_value=[(2,1,6,'',('169.254.169.254',80))]):
            with self.assertRaises(ValueError):public_read.validate_url('http://metadata.example.com')
    def test_reader_public(self):
        with patch('public_read.socket.getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]):
            self.assertEqual(public_read.validate_url('https://example.com'),'https://example.com')
    def test_reader_credentials_rejected(self):
        with self.assertRaises(ValueError):public_read.validate_url('https://name:password@example.com')
    def test_reader_private_port_rejected(self):
        with self.assertRaises(ValueError):public_read.validate_url('https://example.com:18789')
    def test_document_path_boundary(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError): document_read.resolve_inside('/etc/passwd',pathlib.Path(t))
    def test_no_command_secret_leak(self):
        # Patch the actual capture boundary; subprocess.run is no longer used.
        # This must not search PATH for a real executable named 'tool'.
        with patch('process_guard.run_bounded',return_value=__import__('subprocess').CompletedProcess(['tool'],1,b'',b'LEAK_ME')) as capture:
            with self.assertRaises(StackError) as e:stacklib.run(['tool','SECRET_VALUE'])
            capture.assert_called_once()
            self.assertIn('exit code 1',str(e.exception))
            self.assertNotIn('SECRET_VALUE',str(e.exception));self.assertNotIn('LEAK_ME',str(e.exception))

class PackagePolicyTests(unittest.TestCase):
    def test_required_extensions(self):
        manifest=json.loads((ROOT/'manifests/extensions.json').read_text())
        required={e['id'] for e in manifest['sources'] if e['required']}
        self.assertTrue({'gstack','insane-search','prompt-engineering'}<=required)
    def test_only_authorized_star(self):
        m=json.loads((ROOT/'manifests/extensions.json').read_text())
        self.assertEqual(m['star_repositories'],['min9lin9/prompt-engineering-skills'])
    def test_adapters_valid(self):
        for p in (ROOT/'adapters').glob('*/SKILL.md'): extensions.parse_name(p)
    def test_no_privilege_shortcuts(self):
        text=(ROOT/'scripts/remote.py').read_text()
        self.assertNotIn('usermod -aG docker',text)
        self.assertNotIn('dangerouslyDisableDeviceAuth',text)
        self.assertIn('auto_https disable_redirects',text)
    def test_lifecycle_keeps_tailnet(self):
        text=(ROOT/'scripts/operations.py').read_text()
        self.assertNotIn("'tailscale','down'",text)
        self.assertNotIn("'down','-v'",text)
    def test_ssh_strict_host_key(self):
        with tempfile.NamedTemporaryFile() as f:
            a=stack.ssh_args({'ORACLE_HOST':'192.0.2.1','ORACLE_SSH_USER':'ubuntu','ORACLE_SSH_KEY':f.name,'SSH_PORT':'2222'})
            self.assertIn('StrictHostKeyChecking=yes',a)
            self.assertNotIn('StrictHostKeyChecking=accept-new',a)


class IntegrityRegressionTests(unittest.TestCase):
    def test_catalog_subpath_traversal_rejected(self):
        with self.assertRaises(StackError): extensions.source_subpath('../unsafe')
    def test_catalog_absolute_rejected(self):
        with self.assertRaises(StackError): extensions.source_subpath('/etc')
    def test_catalog_id_rejected(self):
        with self.assertRaises(StackError): extensions.validate_catalog_item({'id':'../bad','repo':'owner/repo'})
    def test_catalog_entries_valid(self):
        for item in json.loads((ROOT/'manifests/extensions.json').read_text())['sources']:
            extensions.validate_catalog_item(item)
    def stage_fixture(self, root):
        src=root/'sources/example';src.mkdir(parents=True);(src/'README.md').write_text('fixture')
        item={'id':'example','repo':'owner/repo','commit':'a'*40,'tree_sha256':stacklib.digest_tree(src)}
        stacklib.atom_json(root/'sources.lock.json',{'sources':[item]})
        return src
    def test_source_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=pathlib.Path(t);src=self.stage_fixture(root);(src/'README.md').write_text('altered')
            with self.assertRaises(StackError): extensions.verify_stage(root,reviewed=False)
    def test_stale_review_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=pathlib.Path(t);self.stage_fixture(root)
            stacklib.atom_json(root/'review.receipt.json',{'lock_sha256':'0'*64})
            with self.assertRaises(StackError): extensions.verify_stage(root)
    def test_caddy_build_context_excludes_stack_data(self):
        text=(ROOT/'scripts/remote.py').read_text()
        self.assertIn("builddir=BASE/'caddy-build'",text)
        self.assertIn("write(builddir/'.dockerignore'",text)
        self.assertIn("'up','-d','--no-build'",text)
    def test_reader_bytecode_disabled_in_source_snapshot(self):
        for name in ('public_read.py','fetch_runtime_setup.py'):
            self.assertIn("'PYTHONDONTWRITEBYTECODE':'1'",(ROOT/'scripts'/name).read_text())

if __name__=='__main__':unittest.main(verbosity=2)
