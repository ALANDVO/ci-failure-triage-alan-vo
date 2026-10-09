export type User={subject:string;username:string;roles:string[];csrf_token:string};
export type Run={id:string;external_id:string;attempt:number;repository:string;workflow:string;branch:string;commit:string;started_at:string;job_count:number};
export type Occurrence={run_id:string;external_id:string;attempt:number;commit:string;branch:string;started_at:string;duration_seconds:number;excerpt:string;log_sha256:string};
export type Triage={status:string;owner:string;note:string;revision:number};
export type Group={id:string;repository:string;workflow:string;job:string;test:string;canonical:string;classification:string;occurrences:Occurrence[];failure_count:number;failed_job_minutes:number;estimated_investigation_minutes:number;estimated_impact_minutes:number;flaky_candidate:boolean;scope_failure_rate:number;scope_failure_rate_ci95:number[];observed_outcomes:number;mixed_commit_evidence:{branch:string;commit:string;failed_runs:string[];successful_runs:string[]}[];triage:Triage;first_seen:string;last_seen:string};
export type Report={groups:Group[];summary:{runs:number;jobs:number;outcomes:Record<string,number>;failed_job_minutes:number;total_job_minutes:number;failure_groups:number;flaky_candidates:number};investigation_minutes_per_failure:number;limitations:string[]};
export type Audit={id:number;actor:string;event:string;target:string;details:Record<string,unknown>;created_at:string};
export type Suggestion={group_id:string;run_id:string;quote:string;recommendation:string};
