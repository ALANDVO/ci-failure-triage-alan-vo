import {useState} from 'react';
import {Group} from './types';
import {request} from './api';
export function GroupPanel({group,editable,onSaved,onClose}:{group:Group;editable:boolean;onSaved:()=>void;onClose:()=>void}){
 const [status,setStatus]=useState(group.triage.status);const [owner,setOwner]=useState(group.triage.owner);const [note,setNote]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 async function save(){setBusy(true);setError('');try{await request(`/api/groups/${group.id}`,'PUT',{revision:group.triage.revision,status,owner,note});onSaved();onClose();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <section className="panel selected" aria-label="Failure group detail"><div className="section-head"><h2>{group.job}{group.test&&` / ${group.test}`}</h2><button className="secondary" onClick={onClose}>Close detail</button></div>
 <p className="muted">{group.repository} · {group.workflow} · {group.id}</p><pre>{group.canonical}</pre>
 <div className="metrics"><div><strong>{group.failure_count}</strong> failures</div><div><strong>{group.failed_job_minutes}</strong> failed minutes</div><div><strong>{group.estimated_impact_minutes}</strong> estimated total impact</div></div>
 <p>Scope failure rate: {(group.scope_failure_rate*100).toFixed(1)}% across {group.observed_outcomes} observed success/failure outcomes. Wilson 95% interval: {group.scope_failure_rate_ci95.map(x=>(x*100).toFixed(1)+'%').join(' – ')}. Cancelled/skipped jobs are excluded.</p>
 <p className="notice">{group.flaky_candidate?'Mixed outcomes were observed on the same commit and branch. Investigate environment and infrastructure differences before calling this flaky.':'No same-commit mixed outcomes in the retained sample. This does not establish deterministic behavior.'}</p>
 {group.mixed_commit_evidence.map(x=><details key={x.branch+x.commit}><summary>Mixed outcomes: {x.branch} / {x.commit.slice(0,12)}</summary><p>Failure run IDs: {x.failed_runs.join(', ')}</p><p>Success run IDs: {x.successful_runs.join(', ')}</p></details>)}
 <h3>Human triage · revision {group.triage.revision}</h3><div className="form-grid"><label>Status<select aria-label="Status" value={status} onChange={e=>setStatus(e.target.value)} disabled={!editable}>{['new','investigating','resolved','ignored'].map(s=><option key={s}>{s}</option>)}</select></label><label>Owner<input maxLength={160} value={owner} onChange={e=>setOwner(e.target.value)} disabled={!editable}/></label></div>
 <label>Reason for this change<textarea value={note} minLength={5} maxLength={2000} onChange={e=>setNote(e.target.value)} disabled={!editable}/></label>
 <p className="muted">Last note: {group.triage.note||'No triage recorded'}. Resolution is a human decision; later failures can reopen the group. Concurrent edits require a reload.</p>
 {editable&&<button onClick={save} disabled={busy||note.trim().length<5}>{busy?'Saving…':'Save triage'}</button>}{error&&<p role="alert" className="error">{error}</p>}
 <h3>Evidence ({group.occurrences.length})</h3>{group.occurrences.map(o=><details key={o.run_id}><summary>{o.started_at} · {o.external_id}, attempt {o.attempt} · {o.duration_seconds}s</summary><p>Branch: {o.branch} · Commit: <code>{o.commit}</code></p><pre>{o.excerpt||'No recognized log content available.'}</pre><p className="muted">Original log SHA-256: {o.log_sha256}. Excerpt may be truncated and must be interpreted in context.</p></details>)}
 </section>;
}
