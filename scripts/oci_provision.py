#!/usr/bin/env python3
"""OCI provisioner for the LOCAL Codex host, derived from the launch workflow in
min9lin9/oci-instance-creator. Never run that repository's hardcoded 4/24 cron.
Uses the official OCI Python SDK and carries its own bounded, durable retries.
No cloud/API private key, DNS token, or Tailscale key is copied to a VM.
"""
from __future__ import annotations
import base64, contextlib, fcntl, hashlib, ipaddress, json, os, pathlib, random, re, secrets, sys, time, uuid
from types import SimpleNamespace
from stacklib import StackError, atom_json, private_file, require, run

SHAPE='VM.Standard.A1.Flex'
HOSTKEY_BEGIN='OAS_HOSTKEY_BEGIN'
HOSTKEY_END='OAS_HOSTKEY_END'


def normalized(cfg: dict) -> dict:
    c={k:v for k,v in cfg.items() if v!=''}  # Blank optional template fields mean automatic/default.
    aliases={'OCI_COMPARTMENT_ID':'OCI_COMPARTMENT','OCI_SUBNET_ID':'OCI_SUBNET',
             'OCI_IMAGE_ID':'OCI_IMAGE','OCI_AVAILABILITY_DOMAIN':'OCI_AD'}
    for old,new in aliases.items():
        if c.get(old) and c.get(new) and c[old]!=c[new]: raise StackError('Conflicting OCI setting aliases')
        if c.get(old): c[new]=c[old]
    require(c,'OCI_USER','OCI_FINGERPRINT','OCI_TENANCY','OCI_REGION','OCI_KEY_FILE','DOMAIN')
    for key,kind in [('OCI_USER','user'),('OCI_TENANCY','tenancy')]:
        if not re.fullmatch(r'ocid1\.'+kind+r'\.[A-Za-z0-9.-]+',c[key]): raise StackError('Invalid '+key)
    c.setdefault('OCI_COMPARTMENT',c['OCI_TENANCY'])
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){15}[0-9a-fA-F]{2}',c['OCI_FINGERPRINT']): raise StackError('Invalid OCI API key fingerprint')
    if not re.fullmatch(r'[a-z0-9-]+',c['OCI_REGION']): raise StackError('Invalid OCI_REGION')
    if c.get('OCI_OCPUS','2') != '2' or c.get('OCI_MEMORY_GB','12') != '12':
        raise StackError('This deployment profile is fixed at 2 OCPU / 12 GiB; no capacity upsizing fallback')
    c['OCI_OCPUS']='2';c['OCI_MEMORY_GB']='12'
    boot=int(c.get('OCI_BOOT_VOLUME_GB','50'))
    if not 50<=boot<=200: raise StackError('OCI_BOOT_VOLUME_GB must be 50..200; check shared free quota first')
    c['OCI_BOOT_VOLUME_GB']=str(boot)
    c.setdefault('OCI_INSTANCE_NAME','oracle-ai-stack')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}',c['OCI_INSTANCE_NAME']): raise StackError('Invalid instance name')
    c.setdefault('OCI_CREATE_NETWORK','true' if not c.get('OCI_SUBNET') else 'false')
    if c['OCI_CREATE_NETWORK'] not in ('true','false'): raise StackError('OCI_CREATE_NETWORK must be true or false')
    if c['OCI_CREATE_NETWORK']=='true':
        require(c,'OCI_SSH_ALLOWED_CIDR')
        try: network=ipaddress.ip_network(c['OCI_SSH_ALLOWED_CIDR'],strict=True)
        except ValueError as e: raise StackError('Invalid OCI_SSH_ALLOWED_CIDR') from e
        if network.version!=4 or network.prefixlen<24 or not network.network_address.is_global:
            raise StackError('Initial SSH requires a public IPv4 /24.. /32 CIDR, not internet-wide ingress')
    elif not c.get('OCI_SUBNET'): raise StackError('Provide OCI_SUBNET or enable dedicated network creation')
    tries=int(c.get('OCI_MAX_ATTEMPTS','3'))
    if not 1<=tries<=6: raise StackError('OCI_MAX_ATTEMPTS must be 1..6; no unbounded cron')
    c['OCI_MAX_ATTEMPTS']=str(tries)
    return c


def cloud_init() -> str:
    # Public host fingerprint, obtained later via the signed OCI console-history API.
    text=f'''#cloud-config
ssh_deletekeys: true
ssh_genkeytypes: [ed25519, rsa]
runcmd:
  - [sh, -c, 'echo {HOSTKEY_BEGIN}; ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub; echo {HOSTKEY_END}']
'''
    return base64.b64encode(text.encode()).decode()


def parse_fingerprint(text: str) -> str:
    blocks=re.findall(re.escape(HOSTKEY_BEGIN)+r'\s*\n(.*?)\n'+re.escape(HOSTKEY_END),text.replace('\r',''),re.S)
    if not blocks: raise StackError('SSH fingerprint not yet present in authenticated OCI console output')
    matches=re.findall(r'\b(SHA256:[A-Za-z0-9+/]+)\s+[^\n]*\(ED25519\)',blocks[-1])
    if len(matches)!=1: raise StackError('No unique ED25519 fingerprint in OCI console capture')
    return matches[0]


def error_kind(exc: Exception) -> str:
    code=str(getattr(exc,'code','')); status=getattr(exc,'status',None)
    msg=str(getattr(exc,'message','')).lower()
    if 'out of host capacity' in msg or code in ('OutOfHostCapacity','OutOfCapacity'): return 'CAPACITY'
    if status==429 or code=='TooManyRequests': return 'RATE_LIMIT'
    if status in (401,403) or code in ('NotAuthenticated','NotAuthorizedOrNotFound'): return 'AUTH_OR_ACCESS'
    if code in ('LimitExceeded','QuotaExceeded') or 'limit exceeded' in msg: return 'QUOTA'
    if status in (400,404,409): return 'CONFIG_OR_CONFLICT'
    return 'AMBIGUOUS' # Reconcile the same request, never rotate AD/shape after a timeout.


def safe_error(exc: Exception) -> str:
    return error_kind(exc)+'; OCI response and credential details withheld'


def model(oci,name,**kwargs): return getattr(oci.core.models,name)(**kwargs)


class Provisioner:
    def __init__(self, cfg, state_dir, sdk, *, clients=None, sleep=time.sleep):
        self.cfg=normalized(cfg); self.path=pathlib.Path(state_dir)/'oci.json'; self.oci=sdk; self.sleep=sleep
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {}
        c=self.cfg
        identity=hashlib.sha256((c['OCI_TENANCY']+'|'+c['OCI_COMPARTMENT']+'|'+c['OCI_REGION']+'|'+c['DOMAIN']).encode()).hexdigest()[:24]
        if self.state and self.state.get('deployment_id')!=identity: raise StackError('OCI state belongs to another deployment')
        self.state.setdefault('deployment_id',identity); self.state.setdefault('tokens',{});self.state.setdefault('resources',{})
        self.tags={'oracle-ai-stack':identity,'managed-by':'oracle-ai-stack-v0.3'}
        if clients: self.identity,self.compute,self.network=clients
        else:
            key=pathlib.Path(c['OCI_KEY_FILE']).expanduser(); private_file(key)
            auth={'user':c['OCI_USER'],'fingerprint':c['OCI_FINGERPRINT'],'tenancy':c['OCI_TENANCY'],
                  'region':c['OCI_REGION'],'key_file':str(key)}
            if c.get('OCI_KEY_PASSPHRASE'): auth['pass_phrase']=c['OCI_KEY_PASSPHRASE']
            sdk.config.validate_config(auth)
            policy=sdk.retry.NoneRetryStrategy()
            self.identity=sdk.identity.IdentityClient(auth,retry_strategy=policy,timeout=(10,60))
            self.compute=sdk.core.ComputeClient(auth,retry_strategy=policy,timeout=(10,60))
            self.network=sdk.core.VirtualNetworkClient(auth,retry_strategy=policy,timeout=(10,60))
    def save(self): atom_json(self.path,self.state)
    def listing(self,func,*args,**kwargs):
        return self.oci.pagination.list_call_get_all_results(func,*args,**kwargs).data
    def token(self,key):
        entry=self.state['tokens'].get(key)
        if entry and time.time()-entry['created']>23*3600:
            raise StackError('Retry token approaching expiry; reconcile OCI resources before manually resetting attempt state')
        if not entry:
            entry={'value':uuid.uuid4().hex,'created':time.time()}; self.state['tokens'][key]=entry;self.save()
        return entry['value']
    def owned(self,rows):
        hits=[r for r in rows if (getattr(r,'freeform_tags',None) or {}).get('oracle-ai-stack')==self.state['deployment_id'] and getattr(r,'lifecycle_state','') not in ('TERMINATED','TERMINATING','DELETED','DELETING')]
        if len(hits)>1: raise StackError('Multiple managed resources matched; no additional resource created')
        return hits[0] if hits else None
    def ensure_resource(self,key,list_fn,create_fn,details,list_args):
        # Query tags on every run, including after a lost response/local state write.
        current=self.owned(self.listing(list_fn,**list_args))
        if current:
            previous=self.state['resources'].get(key)
            if previous and previous!=current.id: raise StackError('Managed resource identity changed')
            self.state['resources'][key]=current.id;self.save(); return current
        if self.state['resources'].get(key): raise StackError('Previously created resource missing; no automatic replacement')
        self.state['phase']='CREATING_'+key.upper();self.save()
        try: current=create_fn(details,opc_retry_token=self.token(key)).data
        except Exception as e: raise StackError(safe_error(e)) from e
        self.state['resources'][key]=current.id;self.save();return current
    def prepare_ssh(self):
        c=self.cfg
        key=pathlib.Path(c.get('ORACLE_SSH_KEY') or str(self.path.parent/'ssh/oracle_ed25519')).expanduser()
        if not key.exists():
            key.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],timeout=60)
        private_file(key)
        public=run(['ssh-keygen','-y','-f',str(key)],timeout=15).stdout.decode().strip()
        if c.get('SSH_PUBLIC_KEY') and c['SSH_PUBLIC_KEY'].split()[:2]!=public.split()[:2]: raise StackError('SSH public key does not match the selected private key')
        self.state['ssh_key_path']=str(key);self.state['ssh_public_key']=public; self.save()
        return public
    def preflight(self):
        c=self.cfg
        subscriptions=self.listing(self.identity.list_region_subscriptions,c['OCI_TENANCY'])
        home=[r.region_name for r in subscriptions if r.is_home_region]
        if c['OCI_REGION'] not in home: raise StackError('Only tenancy home region is allowed by this Free Tier deployment policy')
        domains=self.listing(self.identity.list_availability_domains,c['OCI_COMPARTMENT'])
        available=[d.name for d in domains]
        if c.get('OCI_AD'):
            if c['OCI_AD'] not in available: raise StackError('OCI_AD is not in this tenancy/region')
            available=[c['OCI_AD']]
        if not available: raise StackError('No availability domains returned')
        image_id=c.get('OCI_IMAGE') or self.state.get('image_id')
        if image_id:
            image=self.compute.get_image(image_id).data
        else:
            images=self.listing(self.compute.list_images,c['OCI_COMPARTMENT'],operating_system='Canonical Ubuntu',operating_system_version='24.04',shape=SHAPE,sort_by='TIMECREATED',sort_order='DESC')
            images=[i for i in images if getattr(i,'lifecycle_state','AVAILABLE')=='AVAILABLE' and any(s in (getattr(i,'display_name','').lower()) for s in ('aarch64','arm64'))]
            if not images: raise StackError('No official Ubuntu 24.04 ARM image found; provide OCI_IMAGE explicitly')
            image=images[0]
        if image.operating_system!='Canonical Ubuntu' or image.operating_system_version!='24.04': raise StackError('Expected Canonical Ubuntu 24.04 image')
        shapes=self.listing(self.compute.list_shapes,c['OCI_COMPARTMENT'],image_id=image.id)
        if not any(s.shape==SHAPE for s in shapes): raise StackError('Image is not compatible with A1 Flex')
        proposal={'region':c['OCI_REGION'],'compartment':c['OCI_COMPARTMENT'],'ads':available,'image':image.id,
          'shape':SHAPE,'ocpus':2,'memory_gb':12,'boot_volume_gb':int(c['OCI_BOOT_VOLUME_GB']),
          'subnet':c.get('OCI_SUBNET'), 'create_network':c['OCI_CREATE_NETWORK']=='true',
          'ssh_cidr':c.get('OCI_SSH_ALLOWED_CIDR'),'instance_name':c['OCI_INSTANCE_NAME'],
          'free_tier_note':'Resource size is capped, not a billing guarantee. Check aggregate tenancy usage/quota.'}
        atom_json(self.path.parent/'oci-plan.json',proposal)
        return proposal
    def network_ready(self,key,resource):
        names={'vcn':'get_vcn','igw':'get_internet_gateway','route':'get_route_table',
               'security':'get_security_list','subnet':'get_subnet'}
        getter=getattr(self.network,names[key])
        for _ in range(36):
            current=getter(resource.id).data
            state=getattr(current,'lifecycle_state',None)
            if state=='AVAILABLE': return current
            if state not in ('PROVISIONING','UPDATING'):
                raise StackError('Network resource is not usable; preserve its OCID and reconcile')
            self.sleep(5)
        raise StackError('Network resource readiness timeout; resume without creating duplicates')

    def make_network(self):
        c=self.cfg; compartment=c['OCI_COMPARTMENT']
        if c['OCI_CREATE_NETWORK']=='false':
            subnet=self.network.get_subnet(c['OCI_SUBNET']).data
            if subnet.compartment_id!=compartment or subnet.prohibit_public_ip_on_vnic: raise StackError('Subnet must be public and in selected compartment')
            if getattr(subnet,'availability_domain',None):
                raise StackError('Use a regional subnet; AD-specific subnets need an explicit reviewed launch plan')
            # Never rewrite user-owned network/security lists.
            return self.network_ready('subnet',subnet).id
        def details(name,**kw): return model(self.oci,name,compartment_id=compartment,freeform_tags=self.tags,**kw)
        v=self.ensure_resource('vcn',self.network.list_vcns,self.network.create_vcn,
          details('CreateVcnDetails',cidr_block='10.86.0.0/16',display_name=c['OCI_INSTANCE_NAME']+'-vcn',dns_label='oas'+self.state['deployment_id'][:8]),{'compartment_id':compartment})
        v=self.network_ready('vcn',v)
        base={'compartment_id':compartment,'vcn_id':v.id}
        ig=self.ensure_resource('igw',self.network.list_internet_gateways,self.network.create_internet_gateway,
          details('CreateInternetGatewayDetails',vcn_id=v.id,is_enabled=True,display_name='oracle-ai-igw'),base)
        ig=self.network_ready('igw',ig)
        route=model(self.oci,'RouteRule',destination='0.0.0.0/0',destination_type='CIDR_BLOCK',network_entity_id=ig.id)
        rt=self.ensure_resource('route',self.network.list_route_tables,self.network.create_route_table,
          details('CreateRouteTableDetails',vcn_id=v.id,route_rules=[route],display_name='oracle-ai-route'),base)
        rt=self.network_ready('route',rt)
        tcp=model(self.oci,'TcpOptions',destination_port_range=model(self.oci,'PortRange',min=22,max=22))
        ingress=model(self.oci,'IngressSecurityRule',source=c['OCI_SSH_ALLOWED_CIDR'],source_type='CIDR_BLOCK',protocol='6',tcp_options=tcp,is_stateless=False)
        egress=model(self.oci,'EgressSecurityRule',destination='0.0.0.0/0',destination_type='CIDR_BLOCK',protocol='all',is_stateless=False)
        sl=self.ensure_resource('security',self.network.list_security_lists,self.network.create_security_list,
          details('CreateSecurityListDetails',vcn_id=v.id,ingress_security_rules=[ingress],egress_security_rules=[egress],display_name='oracle-ai-private-services'),base)
        sl=self.network_ready('security',sl)
        sn=self.ensure_resource('subnet',self.network.list_subnets,self.network.create_subnet,
          details('CreateSubnetDetails',vcn_id=v.id,cidr_block='10.86.10.0/24',route_table_id=rt.id,
                  security_list_ids=[sl.id],prohibit_public_ip_on_vnic=False,dns_label='agents',display_name='oracle-ai-subnet'),base)
        return self.network_ready('subnet',sn).id
    def existing_instance(self):
        rows=self.listing(self.compute.list_instances,self.cfg['OCI_COMPARTMENT'])
        return self.owned(rows)
    def verify_instance(self,inst,proposal,subnet,public):
        if self.state.get("instance_id") and self.state["instance_id"]!=inst.id:
            raise StackError("Tagged instance differs from recorded instance; no silent adoption")
        if inst.shape!=SHAPE or inst.shape_config.ocpus!=2 or inst.shape_config.memory_in_gbs!=12:
            raise StackError('Existing managed instance has unexpected shape/resources')
        if (getattr(inst,'metadata',None) or {}).get('ssh_authorized_keys','').split()[:2]!=public.split()[:2]:
            raise StackError('Existing managed instance SSH key differs')
        if getattr(inst,'image_id',proposal['image'])!=proposal['image']: raise StackError('Managed instance image mismatch')
        # Subnet is validated on the VNIC after RUNNING.
    def launch(self,proposal,subnet,public):
        signature=hashlib.sha256(json.dumps({**proposal,'subnet':subnet,'ssh_key':public},sort_keys=True).encode()).hexdigest()
        if self.state.get('request_signature') and self.state['request_signature']!=signature:
            raise StackError('Provisioning inputs changed; reconcile prior OCI resources before changing request')
        self.state['request_signature']=signature; self.save()
        inst=self.existing_instance()
        if inst:
            self.verify_instance(inst,proposal,subnet,public)
            self.state['instance_id']=inst.id;self.save();return inst
        if self.state.get('instance_id'): raise StackError('Managed instance disappeared; no silent replacement')
        ads=proposal['ads']; ad=self.state.get('active_ad') or ads[0]
        for attempt in range(int(self.cfg['OCI_MAX_ATTEMPTS'])):
            inst=self.existing_instance()
            if inst: self.verify_instance(inst,proposal,subnet,public);self.state['instance_id']=inst.id;self.save();return inst
            self.state['active_ad']=ad;self.state['phase']='LAUNCH_PENDING';self.save()
            req=model(self.oci,'LaunchInstanceDetails',compartment_id=self.cfg['OCI_COMPARTMENT'],availability_domain=ad,
              display_name=self.cfg['OCI_INSTANCE_NAME'],shape=SHAPE,
              shape_config=model(self.oci,'LaunchInstanceShapeConfigDetails',ocpus=2,memory_in_gbs=12),
              source_details=model(self.oci,'InstanceSourceViaImageDetails',image_id=proposal['image'],boot_volume_size_in_gbs=int(self.cfg['OCI_BOOT_VOLUME_GB'])),
              create_vnic_details=model(self.oci,'CreateVnicDetails',subnet_id=subnet,assign_public_ip=True),
              metadata={'ssh_authorized_keys':public,'user_data':cloud_init()},freeform_tags=self.tags)
            try:
                inst=self.compute.launch_instance(req,opc_retry_token=self.token('launch-'+ad)).data
                self.state['instance_id']=inst.id;self.state['phase']='INSTANCE_ACCEPTED';self.save();return inst
            except Exception as e:
                kind=error_kind(e);self.state['last_error_kind']=kind;self.save()
                if kind in ('AUTH_OR_ACCESS','QUOTA','CONFIG_OR_CONFLICT'): raise StackError(safe_error(e)) from e
                if kind=='CAPACITY':
                    self.state['tokens'].pop('launch-'+ad,None);self.save()
                    ad=ads[(ads.index(ad)+1)%len(ads)]
                # Any ambiguous launch response keeps the same AD and token.
                if attempt+1<int(self.cfg['OCI_MAX_ATTEMPTS']): self.sleep(min(60*(2**attempt),240)+random.randrange(0,11))
        self.state['phase']='WAITING_CAPACITY_OR_RECONCILIATION';self.save()
        raise StackError('Bounded OCI attempts exhausted; rerun provision to reconcile. No cron, paid shape, or region fallback enabled.')
    def wait_running(self,instance_id):
        for _ in range(60):
            inst=self.compute.get_instance(instance_id).data
            if inst.lifecycle_state=='RUNNING': return inst
            if inst.lifecycle_state in ('TERMINATED','TERMINATING','STOPPED'): raise StackError('Instance is not running; manual state review required')
            self.sleep(10)
        raise StackError('Instance not RUNNING within bounded poll; preserved its OCID for resume')
    def public_ip(self,instance_id,subnet):
        attachments=self.listing(self.compute.list_vnic_attachments,self.cfg['OCI_COMPARTMENT'],instance_id=instance_id)
        vnics=[self.network.get_vnic(a.vnic_id).data for a in attachments if getattr(a,'lifecycle_state','ATTACHED')=='ATTACHED']
        hits=[v for v in vnics if v.subnet_id==subnet and v.public_ip]
        if len(hits)!=1: raise StackError('No unique public VNIC in expected subnet')
        ip=ipaddress.ip_address(hits[0].public_ip)
        if not ip.is_global: raise StackError('Instance did not receive a public address')
        return str(ip)
    def fingerprint(self,instance_id):
        # Authenticated OCI control-plane read, never ssh-keyscan trust-on-first-use.
        for _ in range(4):
            capture=self.compute.capture_console_history(model(self.oci,'CaptureConsoleHistoryDetails',instance_id=instance_id)).data
            try:
                for _ in range(20):
                    row=self.compute.get_console_history(capture.id).data
                    if row.lifecycle_state=='SUCCEEDED': break
                    if row.lifecycle_state=='FAILED': raise StackError('OCI console history capture failed')
                    self.sleep(3)
                else: raise StackError('OCI console history capture timed out')
                data=self.compute.get_console_history_content(capture.id).data
                if isinstance(data,bytes): text=data.decode(errors='replace')
                elif isinstance(data,str): text=data
                elif hasattr(data,'text'): text=data.text
                elif hasattr(data,'read'):
                    raw=data.read(2*1024*1024);text=raw.decode(errors='replace') if isinstance(raw,bytes) else raw
                else:raise StackError('Unsupported OCI console response; no SSH trust fallback')
                try: return parse_fingerprint(text)
                except StackError: self.sleep(20)
            finally:
                with contextlib.suppress(Exception): self.compute.delete_console_history(capture.id)
        raise StackError('PENDING_SSH_IDENTITY: verify the host fingerprint in OCI console; no insecure SSH fallback')
    def provision(self):
        proposal=self.preflight();public=self.prepare_ssh()
        # Freeze discovery before any cloud writes so a newly released image cannot
        # alter an in-flight/resumed request. Network inputs are protected too.
        intent=hashlib.sha256(json.dumps({**proposal,'ssh_key':public},sort_keys=True).encode()).hexdigest()
        if self.state.get('intent_sha256') and self.state['intent_sha256']!=intent:
            raise StackError('Provisioning inputs changed; review managed resources before new network writes')
        self.state['intent_sha256']=intent;self.state['image_id']=proposal['image'];self.save()
        subnet=self.make_network()
        inst=self.launch(proposal,subnet,public);self.wait_running(inst.id)
        ip=self.public_ip(inst.id,subnet)
        fingerprint=self.state.get('host_fingerprint') or self.fingerprint(inst.id)
        self.state.update({'phase':'INSTANCE_READY','instance_id':inst.id,'public_ip':ip,'host_fingerprint':fingerprint})
        self.save()
        handoff={'ORACLE_HOST':ip,'ORACLE_SSH_USER':'ubuntu','ORACLE_SSH_KEY':self.state['ssh_key_path'],
                 'SSH_PORT':'22','OCI_INSTANCE_ID':inst.id,'SSH_FINGERPRINT':fingerprint,
                 'DOMAIN':self.cfg['DOMAIN'],'OCI_TENANCY':self.cfg['OCI_TENANCY'],'OCI_REGION':self.cfg['OCI_REGION']}
        atom_json(self.path.parent/'oci-handoff.json',handoff)
        return {'state':'INSTANCE_READY','handoff':str(self.path.parent/'oci-handoff.json'),'free_tier_guaranteed':False}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','provision']);p.add_argument('--state',type=pathlib.Path,required=True);a=p.parse_args()
    cfg=json.load(sys.stdin)
    try: import oci
    except ImportError as e: raise StackError('Run using the prepared local OCI SDK virtual environment') from e
    a.state.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (a.state/'oci.lock').open('a') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as e: raise StackError('Another local OCI provisioning run is active') from e
        worker=Provisioner(cfg,a.state,oci)
        result={'plan':worker.preflight(),'cloud_mutated':False} if a.action=='plan' else worker.provision()
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception as e:
        # SDK exceptions can include request metadata. Never dump their repr/traceback.
        message=str(e) if isinstance(e,StackError) else safe_error(e)
        print(json.dumps({'state':'OCI_BLOCKED','message':message}),file=sys.stderr);sys.exit(2)
