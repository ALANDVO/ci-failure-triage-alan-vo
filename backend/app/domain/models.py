"""Bounded, strict import contracts independent of any CI vendor."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

class Job(StrictBody):
    name: str = Field(min_length=1, max_length=160)
    test: str = Field(default='', max_length=160)
    status: Literal['success','failure','cancelled','skipped']
    duration_seconds: float = Field(ge=0, le=86400)
    log: str = Field(default='', max_length=100000)

    @field_validator('name')
    @classmethod
    def not_blank(cls, value):
        if not value.strip(): raise ValueError('Job name cannot be blank')
        return value.strip()

class Run(StrictBody):
    external_id: str = Field(min_length=1,max_length=160)
    attempt: int = Field(ge=1, le=10000)
    repository: str = Field(min_length=1,max_length=160,pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    workflow: str = Field(min_length=1,max_length=160)
    branch: str = Field(min_length=1,max_length=160)
    commit: str = Field(min_length=7,max_length=64,pattern=r'^[a-fA-F0-9]+$')
    started_at: str
    jobs: list[Job] = Field(min_length=1,max_length=100)

    @field_validator('external_id','workflow','branch')
    @classmethod
    def not_blank(cls,value):
        if not value.strip():raise ValueError('Identifier cannot be blank')
        return value.strip()

    @field_validator('commit')
    @classmethod
    def normalize_commit(cls,value):return value.lower()

    @field_validator('started_at')
    @classmethod
    def timestamp(cls,value):
        try: dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:raise ValueError('started_at must be an ISO 8601 timestamp')
        if dt.tzinfo is None:raise ValueError('started_at requires a timezone offset')
        return dt.astimezone(timezone.utc).isoformat(timespec='seconds')

    @model_validator(mode='after')
    def unique_jobs(self):
        keys=[(j.name,j.test) for j in self.jobs]
        if len(keys)!=len(set(keys)):raise ValueError('Each job and test pair must be unique within a run')
        if sum(len(j.log) for j in self.jobs)>1000000:raise ValueError('Combined logs must not exceed one million characters')
        return self

class Triage(StrictBody):
    revision: int = Field(ge=0)
    status: Literal['new','investigating','resolved','ignored']
    owner: str = Field(default='',max_length=160)
    note: str = Field(min_length=5,max_length=2000)
    @model_validator(mode='after')
    def valid_change(self):
        if len(self.note.strip())<5:raise ValueError('A substantive note is required')
        if self.status!='new' and not self.owner.strip():raise ValueError('Assign an owner before changing status')
        return self

class DeleteRun(StrictBody):
    reason: str = Field(min_length=5,max_length=1000)

class AdviceRequest(StrictBody):
    consent: Literal[True]
