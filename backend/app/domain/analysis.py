"""Observed flakiness and impact ranking; no inferred causality or fabricated cost."""
from collections import defaultdict
from math import sqrt


def wilson(successes,total):
    if not total:return [0.0,1.0]
    z=1.96;p=successes/total;den=1+z*z/total
    center=(p+z*z/(2*total))/den
    half=z*sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [round(max(0,center-half),4),round(min(1,center+half),4)]


def analyze(runs: list[dict], triage: dict | None = None) -> dict:
    triage=triage or {};groups={};scopes=defaultdict(list);total_seconds=0;failed_seconds=0
    counts={s:0 for s in ['success','failure','cancelled','skipped']}
    for run in runs:
        for job in run['jobs']:
            scope=(run['repository'],run['workflow'],run['branch'],job['name'],job['test'])
            scopes[scope].append((run,job));counts[job['status']]+=1;total_seconds+=job['duration_seconds']
            if job['status']!='failure':continue
            failed_seconds+=job['duration_seconds'];gid=job['group_id']
            g=groups.setdefault(gid,{'id':gid,'repository':run['repository'],'workflow':run['workflow'],'job':job['name'],'test':job['test'],'canonical':job['canonical'],'classification':job['classification'],'occurrences':[]})
            g['occurrences'].append({'run_id':run['id'],'external_id':run['external_id'],'attempt':run['attempt'],'commit':run['commit'],'branch':run['branch'],'started_at':run['started_at'],'duration_seconds':job['duration_seconds'],'excerpt':job['excerpt'],'log_sha256':job['log_sha256']})
    indexed_scopes=defaultdict(list)
    for scope,entries in scopes.items():
        indexed_scopes[(scope[0],scope[1],scope[3],scope[4])].append((scope,entries))
    output=[]
    for gid,g in groups.items():
        occurrence_keys={(o['run_id'],g['job'],g['test']) for o in g['occurrences']}
        outcomes=[];mixed=[]
        for scope,entries in indexed_scopes[(g['repository'],g['workflow'],g['job'],g['test'])]:
            if scope[2] not in {o['branch'] for o in g['occurrences']}:continue
            by_commit=defaultdict(list)
            for run,job in entries:
                if job['status'] in {'failure','success'}:
                    outcomes.append(job['status']);by_commit[run['commit']].append((run,job))
            for commit,attempts in by_commit.items():
                relevant=[(r,j) for r,j in attempts if (r['id'],g['job'],g['test']) in occurrence_keys]
                if relevant and any(j['status']=='success' for r,j in attempts):
                    mixed.append({'branch':scope[2],'commit':commit,'failed_runs':[r['id'] for r,j in relevant],'successful_runs':[r['id'] for r,j in attempts if j['status']=='success']})
        n=len(g['occurrences']);duration=sum(x['duration_seconds'] for x in g['occurrences'])
        ordered=sorted(g['occurrences'],key=lambda x:(x['started_at'],x['run_id']))
        output.append(g | {'occurrences':ordered,'failure_count':n,'failed_job_minutes':round(duration/60,2),
             'observed_outcomes':len(outcomes),'scope_failure_rate':round(outcomes.count('failure')/len(outcomes),4) if outcomes else 0,
             'scope_failure_rate_ci95':wilson(outcomes.count('failure'),len(outcomes)),
             'mixed_commit_evidence':mixed,'flaky_candidate':bool(mixed),
             'first_seen':ordered[0]['started_at'],'last_seen':ordered[-1]['started_at'],
             'triage':triage.get(gid,{'status':'new','owner':'','note':'','revision':0})})
    # Wasted job duration is observable; developer time lost is an estimate that
    # requires an explicit team-supplied per-failure investigation assumption.
    output.sort(key=lambda g:(-g['failed_job_minutes'],-g['failure_count'],g['id']))
    return {'groups':output,'summary':{'runs':len(runs),'jobs':sum(counts.values()),'outcomes':counts,'total_job_minutes':round(total_seconds/60,2),'failed_job_minutes':round(failed_seconds/60,2),'failure_groups':len(output),'flaky_candidates':sum(g['flaky_candidate'] for g in output)},
       'limitations':['Imported samples may be incomplete or biased.','Mixed outcomes on the same commit are candidates for flakiness, not proof; environment changes can explain them.','Signatures use the last recognized error line and can group unrelated failures.','Failed job minutes are elapsed job time, not CPU cost or measured human time.']}


def compare(before: list[dict],after: list[dict]) -> dict:
    b=analyze(before);a=analyze(after);bg={g['id']:g for g in b['groups']};ag={g['id']:g for g in a['groups']}
    return {'before':b['summary'],'after':a['summary'],'new_group_ids':sorted(ag.keys()-bg.keys()),'absent_group_ids':sorted(bg.keys()-ag.keys()),
            'persisting':[{'id':k,'canonical':ag[k]['canonical'],'failure_delta':ag[k]['failure_count']-bg[k]['failure_count'],'failed_minutes_delta':round(ag[k]['failed_job_minutes']-bg[k]['failed_job_minutes'],2)} for k in sorted(ag.keys()&bg.keys())],
            'caution':'Absence in the later sample does not prove resolution; compare similar workloads and sample sizes.'}
