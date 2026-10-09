import json
import httpx
import pytest
from app.core.config import Settings
from app.core.errors import AppError
from app.services.advice import AdviceService,parse_suggestions

REPORT={'groups':[{'id':'group1','occurrences':[{'run_id':'run1','excerpt':'Error: connection refused'}]}]}
SUGGESTION={'group_id':'group1','run_id':'run1','quote':'connection refused','recommendation':'Check service readiness before retrying.'}

@pytest.mark.parametrize('provider',['openai-compatible','anthropic','gemini','ollama'])
def test_provider_adapters_and_grounded_response(provider):
    calls=[];raw=json.dumps({'suggestions':[SUGGESTION]})
    def transport(req):
        calls.append(req);body=json.loads(req.content)
        assert 'connection refused' in req.content.decode()
        if provider=='anthropic':
            assert req.url.path=='/v1/messages';assert req.headers['x-api-key']=='fixture-only';return httpx.Response(200,json={'content':[{'type':'text','text':raw}]})
        if provider=='gemini':
            assert ':generateContent' in req.url.path;assert req.headers['x-goog-api-key']=='fixture-only';return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':raw}]}}]})
        assert req.url.path=='/v1/chat/completions';assert body['messages'][0]['role']=='system'
        return httpx.Response(200,json={'choices':[{'message':{'content':raw}}]})
    service=AdviceService(Settings(llm_provider=provider,llm_base_url='https://provider.example/v1',llm_api_key='fixture-only'),httpx.MockTransport(transport))
    assert service.suggest(REPORT)['suggestions']==[SUGGESTION];assert len(calls)==1

@pytest.mark.parametrize('field,value',[('group_id','absent'),('run_id','absent'),('quote','invented evidence'),('quote',''),('recommendation',42)])
def test_invalid_model_evidence_rejected(field,value):
    with pytest.raises(AppError):parse_suggestions(json.dumps({'suggestions':[dict(SUGGESTION,**{field:value})]}),REPORT)

def test_provider_failure_does_not_echo_private_response():
    def fail(req):return httpx.Response(429,text='private provider credential detail')
    service=AdviceService(Settings(llm_api_key='fixture-only'),httpx.MockTransport(fail))
    with pytest.raises(AppError) as exc:service.suggest(REPORT)
    assert 'private provider' not in str(exc.value)

def test_no_credential_means_no_network_request():
    def unexpected(req):raise AssertionError('Network should not run without configuration')
    with pytest.raises(AppError,match='Set LLM_API_KEY'):
        AdviceService(Settings(),httpx.MockTransport(unexpected)).suggest(REPORT)
