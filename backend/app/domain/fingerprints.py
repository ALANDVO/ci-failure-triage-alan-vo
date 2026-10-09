"""Deterministic failure fingerprints with explicit normalization boundaries.

Only known volatile values are removed. Error codes and expected/actual values are
retained: over-grouping semantically different failures would hide regressions.
"""
import hashlib
import json
import re

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
SECRET_ASSIGNMENT = re.compile(r'(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|authorization)\b\s*[:=]\s*(?:["\']?)[^\s,;"\']+')
BEARER = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9_.~+/-]+=*')
TOKEN = re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{16,})\b')
URL_CREDENTIAL = re.compile(r'(https?://)[^\s/@]+:[^\s/@]+@')
ERROR = re.compile(r'(?i)(\b(?:error|exception|failed|failure|fatal|panic|timeout|timed out|assertion)\b|Error:|Exception:)')
UUID = re.compile(r'\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b')
ISO_TIME = re.compile(r'\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?\b')
CLOCK = re.compile(r'^\s*\[?\d\d:\d\d:\d\d(?:\.\d+)?\]?\s*')
ADDRESS = re.compile(r'\b0x[0-9a-fA-F]{6,}\b')
DURATION = re.compile(r'\b\d+(?:\.\d+)?\s*(?:ms|milliseconds|seconds|secs)\b',re.I)
LINE_NUMBER = re.compile(r'(\.(?:py|tsx?|jsx?|go|rs|java|rb|cpp)):\d+(?::\d+)?\b')


def redact(text: str) -> str:
    """Best-effort redaction, not a guarantee that arbitrary logs contain no secrets."""
    text=ANSI.sub('',text).replace('\x00','')
    text=URL_CREDENTIAL.sub(r'\1[REDACTED]@',text)
    text=BEARER.sub('Bearer [REDACTED]',text)
    text=SECRET_ASSIGNMENT.sub(lambda m:m.group(1)+'=[REDACTED]',text)
    return TOKEN.sub('[REDACTED]',text)


def normalize(line: str) -> str:
    line=redact(line)
    line=ISO_TIME.sub('<time>',line)
    line=CLOCK.sub('',line)
    line=UUID.sub('<uuid>',line)
    line=ADDRESS.sub('<address>',line)
    line=DURATION.sub('<duration>',line)
    line=LINE_NUMBER.sub(r'\1:<line>',line)
    return re.sub(r'\s+',' ',line).strip()[:1000]


def signature(log: str, status: str) -> dict:
    lines=redact(log).splitlines()
    candidates=[(i,line) for i,line in enumerate(lines) if ERROR.search(line)]
    if candidates:
        index,line=candidates[-1]
        # The last error is commonly the terminal failure; retain nearby context
        # for human review because this heuristic cannot infer root cause.
        canonical=normalize(line)
        excerpt='\n'.join(lines[max(0,index-2):index+3])[:4000]
        confidence='heuristic'
    else:
        canonical='failure-without-recognized-error' if status=='failure' else status
        excerpt='\n'.join(lines[-8:])[:4000]
        confidence='unclassified'
    return {'canonical':canonical,'excerpt':excerpt,'classification':confidence}


def group_id(repository,workflow,job,test,canonical):
    payload=json.dumps([repository,workflow,job,test,canonical],ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def prepare(run: dict) -> dict:
    result={k:v for k,v in run.items() if k!='jobs'}
    result['jobs']=[]
    for job in run['jobs']:
        derived=signature(job['log'],job['status'])
        result['jobs'].append({k:v for k,v in job.items() if k!='log'} | derived | {
            'group_id':group_id(run['repository'],run['workflow'],job['name'],job['test'],derived['canonical']) if job['status']=='failure' else None,
            'log_sha256':hashlib.sha256(job['log'].encode()).hexdigest(),
            'log_lines':len(job['log'].splitlines())})
    return result
