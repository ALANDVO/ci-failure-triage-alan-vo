import copy,json
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.domain.models import Run
from app.domain.fingerprints import normalize,redact,prepare
from app.domain.analysis import analyze,wilson
from app.domain.exports import csv_cell
from app.services.evaluation import evaluate

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(environment='test',database_path=str(tmp_path/'ci.db'),auth_mode='demo',cookie_secure=False))) as c:
        user=c.post('/api/auth/demo?identity=admin').json();c.headers['X-CSRF-Token']=user['csrf_token'];yield c

@pytest.fixture
def run():
    return {'external_id':'build-1','attempt':1,'repository':'demo/service','workflow':'CI','branch':'main','commit':'abcdef1234567890','started_at':'2026-01-01T12:00:00Z','jobs':[{'name':'tests','test':'checkout','status':'failure','duration_seconds':120.0,'log':'2026-01-01T12:00:00Z Error: timeout after 200ms'}]}

def ingest(c,r):
    response=c.post('/api/runs',json=r);assert response.status_code==201,response.text;return response.json()['id']

def test_import_report_and_redacted_evidence(client,run):
    run['jobs'][0]['log']='api_key=private-value\nError: timeout after 200ms'
    rid=ingest(client,run);data=client.get('/api/runs/'+rid).json()
    assert 'private-value' not in json.dumps(data)
    assert 'log' not in data['jobs'][0]
    report=client.get('/api/report?investigation_minutes=7').json();g=report['groups'][0]
    assert report['summary']['failed_job_minutes']==2
    assert g['estimated_impact_minutes']==9
    assert g['flaky_candidate'] is False

def test_identical_replay_and_conflicting_import(client,run):
    rid=ingest(client,run);assert client.post('/api/runs',json=run).json()=={'id':rid,'replayed':True}
    run['jobs'][0]['log']='Error: different';assert client.post('/api/runs',json=run).status_code==409
    assert len(client.get('/api/runs').json())==1

def test_same_commit_mixed_outcomes_candidate(client,run):
    failure=ingest(client,run);run['attempt']=2;run['jobs'][0]['status']='success';run['jobs'][0]['log']='passed';success=ingest(client,run)
    g=client.get('/api/report').json()['groups'][0]
    assert g['flaky_candidate'];assert g['scope_failure_rate']==.5
    assert g['mixed_commit_evidence'][0]['failed_runs']==[failure]
    assert g['mixed_commit_evidence'][0]['successful_runs']==[success]

@pytest.mark.parametrize('field,value',[('commit','b'*40),('branch','other'),('workflow','nightly'),('repository','demo/other')])
def test_different_scope_or_commit_not_flaky(client,run,field,value):
    ingest(client,run);run['attempt']=2;run[field]=value;run['jobs'][0]['status']='success';ingest(client,run)
    assert not client.get('/api/report').json()['groups'][0]['flaky_candidate']

def test_distinct_failure_codes_not_merged(client,run):
    run['jobs'][0]['log']='Error: status 500';ingest(client,run)
    run['attempt']=2;run['jobs'][0]['log']='Error: status 404';ingest(client,run)
    assert len(client.get('/api/report').json()['groups'])==2

def test_triage_revision_and_audit(client,run):
    ingest(client,run);gid=client.get('/api/report').json()['groups'][0]['id']
    body={'revision':0,'status':'investigating','owner':'Alan','note':'Check the upstream connection pool'}
    first=client.put('/api/groups/'+gid,json=body);assert first.status_code==200;assert first.json()['revision']==1
    assert client.put('/api/groups/'+gid,json=body).status_code==409
    assert client.get('/api/audit').json()[0]['event']=='triage.changed'
    body['revision']=1;body['owner']='';assert client.put('/api/groups/'+gid,json=body).status_code==422

def test_resolution_reopens_only_for_later_failure(client,run):
    from datetime import datetime,timezone,timedelta
    ingest(client,run);gid=client.get('/api/report').json()['groups'][0]['id']
    client.put('/api/groups/'+gid,json={'revision':0,'status':'resolved','owner':'Alan','note':'Patched connection retry handling'})
    run['attempt']=2;ingest(client,run)
    assert client.get('/api/report').json()['groups'][0]['triage']['status']=='resolved'
    run['attempt']=3;run['started_at']=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat();ingest(client,run)
    assert client.get('/api/report').json()['groups'][0]['triage']['status']=='new'

def test_concurrent_identical_import_is_single_record(client,run):
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:client.post('/api/runs',json=run),range(2)))
    assert all(r.status_code==201 for r in results)
    assert sorted(r.json()['replayed'] for r in results)==[False,True]
    assert len(client.get('/api/runs').json())==1

def test_compare_and_exports_and_retention(client,run):
    rid=ingest(client,run);run['attempt']=2;run['started_at']='2026-01-02T12:00:00Z';ingest(client,run)
    compare=client.get('/api/compare?split=2026-01-02T00:00:00Z').json()
    assert compare['before']['runs']==1 and compare['after']['runs']==1
    assert compare['persisting'][0]['failure_delta']==0
    for fmt in ['json','csv','markdown']:
        response=client.get('/api/export/'+fmt);assert response.status_code==200;assert 'attachment' in response.headers['content-disposition']
    assert client.request('DELETE','/api/runs/'+rid,json={'reason':'Archived original evidence offline'}).status_code==204
    assert client.get('/api/runs/'+rid).status_code==404
    assert client.get('/api/audit').json()[0]['event']=='run.deleted'

@pytest.mark.parametrize('field,value',[('started_at','2026-01-01'),('attempt',0),('repository','../../etc/passwd'),('commit','garbage'),('workflow',' ')])
def test_invalid_imports(client,run,field,value):
    run[field]=value;assert client.post('/api/runs',json=run).status_code==422

def test_duplicate_job_pair_rejected(client,run):
    run['jobs'].append(copy.deepcopy(run['jobs'][0]));assert client.post('/api/runs',json=run).status_code==422

def test_authorization_and_csrf(client,run):
    token=client.headers.pop('X-CSRF-Token');assert client.post('/api/runs',json=run).status_code==403
    client.headers['X-CSRF-Token']=token
    user=client.post('/api/auth/demo?identity=reviewer').json();client.headers['X-CSRF-Token']=user['csrf_token']
    rid=ingest(client,run)
    assert client.request('DELETE','/api/runs/'+rid,json={'reason':'Remove previous history'}).status_code==403
    client.post('/api/auth/logout');assert client.get('/api/report').status_code==401

@pytest.mark.parametrize('value',['=cmd()',' +formula','-2+3','@calc','\tformula'])
def test_csv_formula_guard(value):assert csv_cell(value).startswith("'")

def test_evaluation_and_error_code_preservation():
    result=evaluate();assert result['passed']==result['total']==12
    assert normalize('Error: status 500')!=normalize('Error: status 404')
    assert wilson(0,0)==[0,1]
    assert wilson(1,2)[0]<.5<wilson(1,2)[1]

def test_bearer_and_url_redaction():
    assert 'abcXYZ' not in redact('Bearer abcXYZ')
    assert 'password' not in redact('https://user:password@example.com/api')

def test_cancelled_not_treated_as_failure(client,run):
    run['jobs'][0]['status']='cancelled';ingest(client,run);report=client.get('/api/report').json()
    assert report['groups']==[];assert report['summary']['outcomes']['cancelled']==1

def test_unclassified_failure_is_visible(client,run):
    run['jobs'][0]['log']='Process exited without output';ingest(client,run)
    assert client.get('/api/report').json()['groups'][0]['classification']=='unclassified'
