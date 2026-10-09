"""Portable reports with explicit estimates and spreadsheet formula protection."""
import csv
import io
import json
import html
import re
from app.core.errors import AppError


def csv_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text


def markdown_text(value):
    text=html.escape(json.dumps(value,ensure_ascii=False))
    return re.sub(r'([\\`*_\[\]])',r'\\\1',text)


def export(report,format):
    if format=='json':return json.dumps(report,indent=2,ensure_ascii=False),'application/json','json'
    if format=='csv':
        stream=io.StringIO(newline='');writer=csv.writer(stream)
        fields=['id','repository','workflow','job','test','canonical','failure_count','failed_job_minutes','estimated_investigation_minutes','estimated_impact_minutes','flaky_candidate']
        writer.writerow(fields+['status','owner'])
        for group in report['groups']:writer.writerow([csv_cell(group[k]) for k in fields]+[csv_cell(group['triage'][k]) for k in ['status','owner']])
        return stream.getvalue(),'text/csv','csv'
    if format=='markdown':
        lines=['# CI Failure Triage report','',f"Runs: {report['summary']['runs']} · Failed job minutes: {report['summary']['failed_job_minutes']}",
               f"Investigation assumption: {report['investigation_minutes_per_failure']} minutes per failure (estimate, not observed time).",'']
        for g in report['groups']:
            # Escape imported HTML and Markdown syntax in human-readable exports.
            lines += [f"## Group {g['id']}",f"- Scope: {markdown_text([g['repository'],g['workflow'],g['job'],g['test']])}",f"- Signature: {markdown_text(g['canonical'])}",f"- Failures: {g['failure_count']} · Failed minutes: {g['failed_job_minutes']}",f"- Candidate flakiness: {g['flaky_candidate']} · Status: {g['triage']['status']}",'']
        lines+=['## Interpretation']+['- '+x for x in report['limitations']]
        return '\n'.join(lines)+'\n','text/markdown','md'
    raise AppError(400,'unsupported_format','Choose json, csv or markdown')
