"""Transactional imports and auditable human triage over derived evidence."""
import hashlib
import json
import uuid
from app.core.db import utcnow
from app.core.errors import AppError
from app.domain.fingerprints import prepare
from app.domain.analysis import analyze, compare

SCHEMA='''
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, import_key TEXT UNIQUE NOT NULL, digest TEXT NOT NULL,
 repository TEXT NOT NULL, branch TEXT NOT NULL, started_at TEXT NOT NULL,
 data TEXT NOT NULL, imported_at TEXT NOT NULL, imported_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage (
 group_id TEXT PRIMARY KEY, status TEXT NOT NULL, owner TEXT NOT NULL,
 note TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, event TEXT NOT NULL,
 target TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_scope ON runs(repository,branch,started_at);
'''

class TriageService:
    def __init__(self,db):
        self.db=db
        with db._lock:db._conn.executescript(SCHEMA)

    def audit_write(self,conn,actor,event,target,details):
        count=conn.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
        if count>=20000:raise AppError(409,'audit_capacity','Audit capacity reached; export and archive this workspace before further mutations')
        conn.execute('INSERT INTO audit(actor,event,target,details,created_at) VALUES(?,?,?,?,?)',(actor,event,target,json.dumps(details),utcnow()))

    def ingest(self,run,actor):
        # The digest covers the full incoming record, including original logs.
        # Only bounded redacted excerpts and a hash survive ingestion.
        digest=hashlib.sha256(json.dumps(run,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        key=json.dumps([run['repository'],run['workflow'],run['external_id'],run['attempt']])
        data=prepare(run);rid=uuid.uuid4().hex;data['id']=rid
        with self.db.transaction() as conn:
            existing=conn.execute('SELECT id,digest FROM runs WHERE import_key=?',(key,)).fetchone()
            if existing:
                if existing['digest']!=digest:raise AppError(409,'replay_conflict','This run attempt already exists with different content; use its original data or a distinct attempt')
                return {'id':existing['id'],'replayed':True}
            if conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]>=500:raise AppError(409,'run_capacity','Maximum 500 runs per workspace; export and remove old runs first')
            conn.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',(rid,key,digest,run['repository'],run['branch'],run['started_at'],json.dumps(data),utcnow(),actor))
            self.audit_write(conn,actor,'run.imported',rid,{'repository':run['repository'],'jobs':len(run['jobs']),'digest':digest})
            for gid in sorted({j['group_id'] for j in data['jobs'] if j['group_id']}):
                old=conn.execute('SELECT * FROM triage WHERE group_id=?',(gid,)).fetchone()
                if old and old['status']=='resolved' and run['started_at']>old['updated_at']:
                    conn.execute("UPDATE triage SET status='new',revision=revision+1,note=?,updated_at=? WHERE group_id=?",('New failure observed after resolution',utcnow(),gid))
                    self.audit_write(conn,actor,'triage.reopened',gid,{'run_id':rid,'previous_revision':old['revision']})
        return {'id':rid,'replayed':False}

    def _runs(self,conn,repository='',branch=''):
        rows=conn.execute('SELECT data FROM runs WHERE (?="" OR repository=?) AND (?="" OR branch=?) ORDER BY started_at,id',(repository,repository,branch,branch)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def runs(self,repository='',branch=''):
        with self.db._lock:return self._runs(self.db._conn,repository,branch)

    def get(self,rid):
        r=self.db.query_one('SELECT data,imported_at,imported_by FROM runs WHERE id=?',(rid,))
        if not r:raise AppError(404,'run_not_found','Run does not exist')
        return json.loads(r['data'])|{'imported_at':r['imported_at'],'imported_by':r['imported_by']}

    def report(self,repository='',branch='',investigation_minutes=10.0):
        with self.db.transaction() as conn:
            records=self._runs(conn,repository,branch)
            triage={r['group_id']:dict(r) for r in conn.execute('SELECT * FROM triage')}
        result=analyze(records,triage)
        for g in result['groups']:
            g['estimated_investigation_minutes']=round(g['failure_count']*investigation_minutes,2)
            g['estimated_impact_minutes']=round(g['failed_job_minutes']+g['estimated_investigation_minutes'],2)
        result['groups'].sort(key=lambda g:(-g['estimated_impact_minutes'],g['id']))
        return result|{'investigation_minutes_per_failure':investigation_minutes}

    def transition(self,gid,body,actor):
        with self.db.transaction() as conn:
            all_groups={j['group_id'] for r in self._runs(conn) for j in r['jobs'] if j['group_id']}
            if gid not in all_groups:raise AppError(404,'group_not_found','Failure group has no retained evidence')
            old=conn.execute('SELECT * FROM triage WHERE group_id=?',(gid,)).fetchone()
            revision=old['revision'] if old else 0
            if revision!=body['revision']:raise AppError(409,'revision_conflict','Triage changed; reload the board before saving')
            previous=old['status'] if old else 'new';now=utcnow()
            conn.execute('INSERT INTO triage VALUES(?,?,?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET status=excluded.status,owner=excluded.owner,note=excluded.note,revision=excluded.revision,updated_at=excluded.updated_at',
                         (gid,body['status'],body['owner'].strip(),body['note'].strip(),revision+1,now))
            self.audit_write(conn,actor,'triage.changed',gid,{'from':previous,'to':body['status'],'owner':body['owner'].strip(),'note':body['note'].strip(),'revision':revision+1})
        return {'id':gid,'status':body['status'],'owner':body['owner'].strip(),'note':body['note'].strip(),'revision':revision+1,'updated_at':now}

    def delete(self,rid,reason,actor):
        if len(reason.strip())<5:raise AppError(422,'reason_required','Provide a substantive retention reason')
        with self.db.transaction() as conn:
            old=conn.execute('SELECT digest FROM runs WHERE id=?',(rid,)).fetchone()
            if not old:raise AppError(404,'run_not_found','Run does not exist')
            self.audit_write(conn,actor,'run.deleted',rid,{'reason':reason.strip(),'digest':old['digest']})
            conn.execute('DELETE FROM runs WHERE id=?',(rid,))

    def audit(self):
        return [dict(r)|{'details':json.loads(r['details'])} for r in self.db.query('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]

    def compare(self,split,repository='',branch=''):
        records=self.runs(repository,branch)
        return compare([r for r in records if r['started_at']<split],[r for r in records if r['started_at']>=split])|{'split':split}
