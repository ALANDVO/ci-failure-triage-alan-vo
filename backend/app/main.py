"""CI Failure Triage authenticated HTTP interface."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings,load_settings,validate_settings,ensure_db_dir
from app.core.db import Database
from app.core.auth import router as auth_router, authorize, OIDCClient
from app.core.body_limit import BodyLimit
from app.core.errors import AppError
from app.domain.models import Run,Triage,DeleteRun,AdviceRequest
from app.domain.exports import export
from app.services.triage import TriageService
from app.services.advice import AdviceService
from app.services.evaluation import evaluate


def create_app(settings:Settings|None=None,oidc_transport=None,llm_transport=None):
    settings=settings or load_settings()
    @asynccontextmanager
    async def lifespan(app):
        validate_settings(settings);ensure_db_dir(settings.database_path)
        db=Database(settings.database_path);app.state.db=db;app.state.triage=TriageService(db)
        try:yield
        finally:db.close()
    app=FastAPI(title='CI Failure Triage — Alan Vo',version='1.0.1',lifespan=lifespan)
    app.state.settings=settings;app.state.oidc=OIDCClient(settings,oidc_transport)
    app.state.advice=AdviceService(settings,llm_transport)
    app.add_middleware(BodyLimit,limit=settings.max_upload_bytes)
    app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,
        allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Content-Type','X-CSRF-Token'])
    app.include_router(auth_router)
    @app.exception_handler(AppError)
    async def error(request,exc):return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status)
    @app.middleware('http')
    async def headers(request,call_next):
        response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='same-origin'
        return response
    def service(request):return request.app.state.triage
    def actor(request,role='viewer'):return authorize(request,role)['subject']
    @app.get('/api/health')
    def health():return {'status':'ok','version':'1.0.1'}
    @app.get('/api/runs')
    def runs(request:Request,repository:str=Query('',max_length=160),branch:str=Query('',max_length=160)):
        actor(request);return [{k:v for k,v in r.items() if k!='jobs'}|{'job_count':len(r['jobs'])} for r in service(request).runs(repository,branch)]
    @app.post('/api/runs',status_code=201)
    def ingest(body:Run,request:Request):return service(request).ingest(body.model_dump(),actor(request,'reviewer'))
    @app.get('/api/runs/{rid}')
    def get(rid:str,request:Request):actor(request);return service(request).get(rid)
    @app.delete('/api/runs/{rid}',status_code=204)
    def delete(rid:str,body:DeleteRun,request:Request):service(request).delete(rid,body.reason,actor(request,'admin'));return Response(status_code=204)
    @app.get('/api/report')
    def report(request:Request,repository:str=Query('',max_length=160),branch:str=Query('',max_length=160),investigation_minutes:float=Query(10,ge=0,le=480,allow_inf_nan=False)):
        actor(request);return service(request).report(repository,branch,investigation_minutes)
    @app.put('/api/groups/{gid}')
    def triage(gid:str,body:Triage,request:Request):return service(request).transition(gid,body.model_dump(),actor(request,'reviewer'))
    @app.get('/api/compare')
    def comparison(request:Request,split:str,repository:str=Query('',max_length=160),branch:str=Query('',max_length=160)):
        actor(request)
        try:
            dt=datetime.fromisoformat(split.replace('Z','+00:00'))
            if dt.tzinfo is None:raise ValueError()
        except ValueError:raise AppError(422,'split_time','Split must be an ISO timestamp with a timezone')
        return service(request).compare(dt.astimezone(timezone.utc).isoformat(timespec='seconds'),repository,branch)
    @app.get('/api/export/{format}')
    def download(format:str,request:Request,repository:str=Query('',max_length=160),branch:str=Query('',max_length=160),investigation_minutes:float=Query(10,ge=0,le=480,allow_inf_nan=False)):
        actor(request);text,mime,suffix=export(service(request).report(repository,branch,investigation_minutes),format)
        return Response(text,media_type=mime,headers={'Content-Disposition':f'attachment; filename="ci-triage.{suffix}"'})
    @app.get('/api/audit')
    def audit(request:Request):actor(request);return service(request).audit()
    @app.get('/api/evaluation')
    def evaluation(request:Request):actor(request);return evaluate()
    @app.post('/api/advice')
    def advice(body:AdviceRequest,request:Request,repository:str=Query('',max_length=160),branch:str=Query('',max_length=160)):
        actor(request,'reviewer');return app.state.advice.suggest(service(request).report(repository,branch))
    return app

app=create_app()
