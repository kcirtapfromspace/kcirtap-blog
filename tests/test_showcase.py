import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from showcase.store import Store, GateError, canonical, digest, verify_owner
from showcase import domain, jev, release, github
from showcase.server import make_server

POLICY = json.loads((Path(__file__).parents[1] / 'showcase/policy.json').read_bytes())
COMMIT = 'a' * 40
PIXELS = b'\x89PNG\r\n\x1a\nsynthetic-test-pixels'  # Unit fixture, NEVER production evidence.


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'private')
        self.task = 'TEST-001'
        self.initial = {'task_id': self.task, 'audience': 'Reader', 'problem': 'Cannot perform X', 'before': 'No X', 'after': 'Can X', 'requirements': [{'id': 'R1', 'behavior': 'X', 'action': 'Click X', 'expected': 'See X'}]}
        self.contract = domain.contract(self.store, self.initial)
        self.article = self.store.put(b'+++\ntitle="X"\n+++\n## Result\n![Observed X](figure-result.png)\n')
        self.image = self.store.put(PIXELS)
        self.outcome = self.store.put({'observed': 'Saw X', 'contradictions': [], 'provenance': {'recorder':'test fixture', 'captured_at':'2026-10-20', 'method':'unit fixture', 'environment':'test', 'steps':['Click X'], 'classification':'controlled-demonstration', 'commits':[COMMIT]}})
        self.source = [{'commit': COMMIT, 'path':'x.py', 'content_hash':self.store.put(b'def x():\n    return True\n'), 'repository':'example/public', 'role':'changed'}]
        self.value = {'task_id': self.task, 'slug':'example', 'contract_hash':self.contract['contract_hash'], 'article_hash':self.article, 'commits':[COMMIT], 'source_manifest':self.source, 'workflow':'Click X to see X', 'limitations':['Fixture only'], 'evidence':[{'requirement_id':'R1','commits':[COMMIT], 'original_hash':self.image, 'inline_hash':self.image, 'outcome_hash':self.outcome, 'section':'Result', 'figure':'figure-result.png', 'classification':'controlled-demonstration','limitations':['Fixture only']}]}
        domain.add_candidate(self.store, self.task, self.value)

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def source_capture(self):
        self.store.append('source-capture',self.task,{'commit':COMMIT,'manifest_hash':self.store.put(self.source)})

    def owner_keys(self):
        key = self.root / 'owner-key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
        signers = self.root / 'allowed-signers'
        signers.write_text('owner ' + key.with_suffix('.pub').read_text())
        return key,signers

    def envelope(self, p, key):
        payload = self.root / 'payload.json'
        payload.write_bytes(canonical(p))
        sig = Path(str(payload)+'.sig')
        if sig.exists(): sig.unlink()
        subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n','kcirtap-showcase',str(payload)],check=True,capture_output=True)
        return {'payload':p,'signature':sig.read_text()}

    def fake(self, req, key):
        answers={}
        for k,q in req['questions'].items():
            choices=list(q['criteria'])
            answers[k]={'type':'choice','choice':choices[0], 'confidence':0.95,'probabilities':{v:float(i==0) for i,v in enumerate(choices)}}
        return 200,canonical({'model':req['model'],'answers':answers,'usage':{'input_tokens':1,'output_tokens':1}}),{}

    def test_private_state_rejected_in_git(self):
        gitdir=self.root/'git';gitdir.mkdir();(gitdir/'.git').mkdir()
        with self.assertRaises(GateError): Store(gitdir/'private')

    def test_append_only_and_object_tamper(self):
        with self.assertRaises(sqlite3.IntegrityError): self.store.db.execute('DELETE FROM events')
        (self.store.blobs/self.article).write_bytes(b'changed')
        with self.assertRaises(GateError): self.store.get(self.article)

    def test_contract_cannot_weaken_after_landing_or_before(self):
        domain.land(self.store,self.task,{'contract_hash':self.contract['contract_hash'],'prs':[{'task_id':self.task,'merged_at':'2026-10-20','merge_commit':COMMIT}]})
        value=copy.deepcopy(self.initial);value['requirements'][0]['expected']='Anything'
        with self.assertRaises(GateError): domain.contract(self.store,value)

    def test_legacy_requirements_need_person(self):
        v=copy.deepcopy(self.initial);v['task_id']='LEGACY-001';v['legacy']=True
        c=domain.contract(self.store,v)
        with self.assertRaises(GateError): domain.land(self.store,'LEGACY-001',{'contract_hash':c['contract_hash'],'prs':[{'task_id':'LEGACY-001','merged_at':'2026-10-20','merge_commit':COMMIT}]})

    def test_owner_auth_signature_and_replay(self):
        key,signers=self.owner_keys()
        p={'actor':'model','at':'2026-10-20','kind':'choice','task_id':self.task,'action':'promote','candidate_hash':self.store.latest(self.task,'candidate')['candidate_hash'],'previous':None}
        with self.assertRaises(GateError): domain.owner_action(self.store,self.envelope(p,key),signers)
        p['actor']='owner';env=self.envelope(p,key)
        domain.owner_action(self.store,env,signers)
        with self.assertRaises(GateError): domain.owner_action(self.store,env,signers)
        env['payload']['action']='skip'
        with self.assertRaises(GateError): domain.owner_action(self.store,env,signers)

    def test_correction_is_immutable_and_unselected_pending(self):
        self.assertIn('Choose promote', ' '.join(domain.gate(self.store,self.task,POLICY)['pending_owner']))
        key,signers=self.owner_keys()
        p={'actor':'owner','at':'2026-10-20','kind':'choice','task_id':self.task,'action':'defer','candidate_hash':self.store.latest(self.task,'candidate')['candidate_hash'],'previous':None}
        domain.owner_action(self.store,self.envelope(p,key),signers)
        p['action']='promote';p['at']='2026-10-21';p['previous']=self.store.events(self.task,'choice')[-1]['hash']
        domain.owner_action(self.store,self.envelope(p,key),signers)
        self.assertEqual(len(self.store.events(self.task,'choice')),2)

    def test_text_review_never_approves_pixels(self):
        errors=domain.evidence_errors(self.store,self.task)
        self.assertTrue(any('pixel' in x for x in errors))
        jev.run_review(self.store,self.task,'evidence',POLICY,send=self.fake)
        self.assertTrue(any('pixel' in x for x in domain.evidence_errors(self.store,self.task)))

    def test_missing_figure_commit_and_contradiction(self):
        v=copy.deepcopy(self.value);v['evidence'][0]['commits']=['b'*40];v['evidence'][0]['section']='Other'
        outcome=json.loads(self.store.get(self.outcome));outcome['contradictions']=['X did not work'];v['evidence'][0]['outcome_hash']=self.store.put(outcome)
        domain.add_candidate(self.store,self.task,v)
        errors=' '.join(domain.evidence_errors(self.store,self.task))
        for part in ('commits','inline figure','contradictory'): self.assertIn(part,errors)

    def test_source_coverage_and_bounded_complete_chunks(self):
        self.assertTrue(domain.source_errors(self.store,self.value))
        self.source_capture();self.assertFalse(domain.source_errors(self.store,self.value))
        ch=jev.chunks(self.store,self.source,max_chars=20,overlap_lines=1)
        seen=set()
        for c in ch: seen.update(range(c['start'],c['end']+1))
        self.assertEqual(seen,{1,2})

    def test_feedback_isolation(self):
        jev.run_review(self.store,self.task,'scope',POLICY,send=self.fake)
        old=domain.review_input_hashes(self.store,self.task)
        self.store.append('choice','ANOTHER-001',{'actor':'owner','action':'lower'})
        new=domain.review_input_hashes(self.store,self.task)
        self.assertEqual({k:old[k] for k in ('scope','evidence','writing')},{k:new[k] for k in ('scope','evidence','writing')})
        self.assertNotEqual(old['ranking'],new['ranking'])
        for stage in ('scope','evidence','writing'):
            self.assertNotIn('owner_ranking_examples',str(list(jev.requests(self.store,self.task,stage,POLICY['model']))))

    def test_article_edit_invalidates_evidence_writing_only(self):
        old=domain.review_input_hashes(self.store,self.task)
        v=copy.deepcopy(self.value);v['article_hash']=self.store.put(b'Changed')
        domain.add_candidate(self.store,self.task,v)
        new=domain.review_input_hashes(self.store,self.task)
        self.assertEqual(old['scope'],new['scope']);self.assertNotEqual(old['evidence'],new['evidence']);self.assertNotEqual(old['writing'],new['writing'])

    def test_completed_unfavorable_response_is_not_resampled(self):
        def low(req,key):
            status,body,h=self.fake(req,key);d=json.loads(body)
            for a in d['answers'].values(): a['confidence']=0.3
            return status,canonical(d),h
        result=jev.run_review(self.store,self.task,'writing',POLICY,send=low)
        def fail(*args): self.fail('completed response was resampled')
        self.assertEqual(result,jev.run_review(self.store,self.task,'writing',POLICY,send=fail))
        self.assertTrue(domain.gate(self.store,self.task,POLICY)['low_confidence'])

    def test_retries_preserve_failed_transports(self):
        calls=[]
        def send(req,key):
            calls.append(1)
            return (429,b'{"error":"rate limit"}',{}) if len(calls)==1 else self.fake(req,key)
        result=jev.run_review(self.store,self.task,'writing',POLICY,send=send,sleep=lambda _:None)
        self.assertEqual(result['status'],'complete')
        self.assertEqual([e['payload']['status'] for e in self.store.events(self.task,'jev-attempt')],['transport-rejected','complete'])

    def test_invalid_200_and_lost_response_do_not_resample(self):
        result=jev.run_review(self.store,self.task,'writing',POLICY,send=lambda *_:(200,b'{"answers":{}}',{}))
        self.assertEqual(result['status'],'incomplete')
        with self.assertRaises(GateError): jev.run_review(self.store,self.task,'writing',POLICY,send=self.fake)
        self.assertTrue(domain.gate(self.store,self.task,POLICY)['incomplete_review'])

    def test_missing_key_cannot_fake_completed_review(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(GateError): jev.run_review(self.store,self.task,'writing',POLICY)

    def test_rank_requires_independent_source_review(self):
        with self.assertRaises(GateError): jev.run_review(self.store,self.task,'ranking',POLICY,send=self.fake)

    def test_discovery_groups_task_and_never_infers_rejection(self):
        pr={'number':1,'title':'Capability','body':'Task: FLOW-001','state':'closed','merged_at':'2026-10-20','merge_commit_sha':COMMIT,'head':{'sha':COMMIT},'updated_at':'9999-01-01'}
        github.discover(self.store,['example/public'],read=lambda _:[pr])
        self.assertEqual(self.store.events(kind='discovery')[-1]['task'],'FLOW-001')
        self.assertTrue(domain.obligations(self.store,POLICY))
        self.assertFalse(self.store.events(kind='choice'))

    def test_release_cannot_prepare_with_pending_gates(self):
        with self.assertRaises(GateError): release.prepare(self.store,[self.task],POLICY,self.root,'1.0.0')
        with self.assertRaises(GateError): release.prepare(self.store,[self.task],POLICY,self.root,'1.0.0-rc.1')

    def test_queue_auth_host_origin_and_escape(self):
        server=make_server(self.store,POLICY,'t'*40,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin=f'http://127.0.0.1:{server.server_port}'
        def call(path='/',data=None,headers={}): return urlopen(Request(origin+path,data=data,headers=headers),timeout=5)
        try:
            with self.assertRaises(HTTPError) as c: call()
            self.assertEqual(c.exception.code,401)
            with self.assertRaises(HTTPError) as c: call(headers={'Host':'evil.example'})
            self.assertEqual(c.exception.code,403)
            with self.assertRaises(HTTPError): call('/login',b'token='+b't'*40,{'Origin':'http://evil.example','Content-Type':'application/x-www-form-urlencoded'})
            login=call('/login',b'token='+b't'*40,{'Origin':origin,'Content-Type':'application/x-www-form-urlencoded'})
            cookie=login.headers['Set-Cookie'].split(';')[0]
            self.assertIn(b'Owner editorial desk',call(headers={'Cookie':cookie}).read())
            with self.assertRaises(HTTPError): call('/choice-draft',b'task=TEST-001&action=promote',{'Cookie':cookie,'Content-Type':'application/x-www-form-urlencoded'})
        finally:
            server.shutdown();server.server_close();thread.join()


class Publication(unittest.TestCase):
    def test_stable_signature_catalog_binding_preservation_and_prerelease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();trust=root/'allowed';key=root/'key'
            def cmd(*args): return subprocess.run(args,cwd=repo,check=True,capture_output=True)
            cmd('git','init','-q');cmd('git','config','user.name','Unit Test');cmd('git','config','user.email','unit@example.invalid')
            cmd('ssh-keygen','-q','-t','ed25519','-N','','-f',str(key))
            trust.write_text('owner '+key.with_suffix('.pub').read_text())
            (repo/'showcase').mkdir();folder=repo/'showcase-publication'/'story';folder.mkdir(parents=True)
            (folder/'index.md').write_text('+++\ntitle="Story"\n+++\nObserved result')
            story={'slug':'story','files':{'index.md':digest((folder/'index.md').read_bytes())}}
            previous=None
            def tag(version,stories):
                c={'schema':1,'version':version,'previous_catalog_hash':previous,'stories':stories}
                (repo/'showcase/catalog.json').write_bytes(canonical(c))
                cmd('git','add','.');cmd('git','commit','-qm',version)
                commit=cmd('git','rev-parse','HEAD').stdout.decode().strip()
                message=canonical({'schema':1,'kind':'prerelease' if '-rc.' in version else 'stable','blog_commit':commit,'catalog_hash':digest(canonical(c)),'version':version}).decode()
                cmd('git','-c','gpg.format=ssh','-c',f'user.signingkey={key}','tag','-s','showcase/v'+version,'-m',message)
                return c
            c=tag('1.0.0-rc.1',[story])
            # Prereleases are retained, never selected.
            self.assertEqual(release.stable_catalog(repo,trust)[0],release.EMPTY)
            c=tag('1.0.0',[story]);previous=digest(c)
            output=root/'public';release.sync_public(repo,output,trust)
            self.assertEqual((output/'story/index.md').read_bytes(),(folder/'index.md').read_bytes())
            # A signed deletion still violates the catalog preservation rule.
            tag('1.1.0',[])
            with self.assertRaises(GateError): release.stable_catalog(repo,trust)

    def test_unsigned_catalog_and_lightweight_tag_do_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'showcase').mkdir();(repo/'showcase/catalog.json').write_text('{"stories":[{"slug":"bad"}]}')
            result=release.sync_public(repo,root/'public')
            self.assertEqual(result['version'],'0.0.0')
            self.assertFalse((root/'public'/'bad').exists())

class CalibrationAndFreshness(unittest.TestCase):
    setUp = Case.setUp
    tearDown = Case.tearDown
    owner_keys = Case.owner_keys
    envelope = Case.envelope
    fake = Case.fake
    source_capture = Case.source_capture
    # These are isolated synthetic unit records, never feature demonstrations.
    def test_calibration_needs_owner_labels_and_original_receipts(self):
        from showcase.calibration import validate
        key,signers=self.owner_keys()
        p={'actor':'owner','at':'2026-10-20','kind':'calibration','task_id':'POLICY','previous':None,'policy_hash':digest(POLICY),'examples':[]}
        with self.assertRaises(GateError): validate(self.store,POLICY,self.envelope(p,key),signers)
        examples=[]
        for stage in domain.STAGES:
            for i in range(12):
                req={'model':POLICY['model'],'state':f'synthetic test {stage} {i}','questions':{'q':jev.choice('Synthetic?',{'supported':'Yes','missing':'No'})}}
                response=self.fake(req,None)[1]
                rh=self.store.put(req);sh=self.store.put(response)
                self.store.append('jev-attempt','POLICY',{'request_hash':rh,'response_hash':sh,'status':'complete'})
                examples.append({'stage':stage,'request_hash':rh,'response_hash':sh,'labels':{'q':'supported'},'split':'held-out','label_recorded_before_review':True})
        p['examples']=examples
        validate(self.store,POLICY,self.envelope(p,key),signers)
        self.assertEqual(self.store.latest('POLICY','calibration')['policy_hash'],digest(POLICY))
        # Calibration cannot waive missing observed outcomes or missing source.
        result=domain.gate(self.store,self.task,POLICY)
        self.assertFalse(result['ready']);self.assertTrue(result['feature_evidence']);self.assertTrue(result['incomplete_review'])

    def test_visual_signature_is_stale_after_article_change(self):
        key,signers=self.owner_keys()
        p={'actor':'owner','at':'2026-10-20','kind':'visual-review','task_id':self.task,'previous':None,'candidate_hash':self.store.latest(self.task,'candidate')['candidate_hash'],'media':{self.image:self.image},'approved':True,'safe_for_public':True}
        domain.owner_action(self.store,self.envelope(p,key),signers)
        self.assertFalse(any('pixel' in e for e in domain.evidence_errors(self.store,self.task)))
        v=copy.deepcopy(self.value);v['article_hash']=self.store.put(self.store.get(self.article)+b'New assertion')
        domain.add_candidate(self.store,self.task,v)
        self.assertTrue(any('pixel' in e for e in domain.evidence_errors(self.store,self.task)))

    def test_feedback_requires_fresh_ranking_without_rerunning_scope(self):
        jev.run_review(self.store,self.task,'scope',POLICY,send=self.fake)
        jev.run_review(self.store,self.task,'ranking',POLICY,send=self.fake)
        count=len(self.store.events(kind='jev-attempt'))
        self.store.append('choice','OTHER-001',{'action':'lower','actor':'owner'})
        self.assertTrue(any('ranking' in x for x in domain.gate(self.store,self.task,POLICY)['incomplete_review']))
        def fail(*_): self.fail('Source resampled because of feedback')
        jev.run_review(self.store,self.task,'scope',POLICY,send=fail)
        self.assertEqual(count,len(self.store.events(kind='jev-attempt')))

    def test_prerelease_cannot_complete_launch(self):
        with self.assertRaises(GateError): release.verify_live(self.store,self.root,'showcase/v1.0.0-rc.1',None,lambda _:b'')

    def test_complete_proof_does_not_waive_jev_or_owner(self):
        self.source_capture()
        domain.land(self.store,self.task,{'contract_hash':self.contract['contract_hash'],'prs':[{'task_id':self.task,'merged_at':'2026-10-20','merge_commit':COMMIT}]})
        key,signers=self.owner_keys()
        p={'actor':'owner','at':'2026-10-20','kind':'visual-review','task_id':self.task,'previous':None,'candidate_hash':self.store.latest(self.task,'candidate')['candidate_hash'],'media':{self.image:self.image},'approved':True,'safe_for_public':True}
        domain.owner_action(self.store,self.envelope(p,key),signers)
        result=domain.gate(self.store,self.task,POLICY)
        self.assertFalse(result['feature_evidence']);self.assertTrue(result['incomplete_review']);self.assertTrue(result['pending_owner']);self.assertFalse(result['ready'])
