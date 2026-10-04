"""Headless API contracts. Fixtures are never installed as application content."""
import asyncio
import threading
from dataclasses import replace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from apprentice.config import Settings
from apprentice.domain import Evidence, Knowledge, Observation, Session
from apprentice.store import SessionStore
from backend.server import create_app
from backend.service import Service
from backend.training import generate, Exercises, Exercise


@pytest.fixture
def api(tmp_path):
    with TestClient(create_app(tmp_path, "test-token", Settings())) as client:
        client.headers["Authorization"] = "Bearer test-token"
        yield client


def command(api, name, **data):
    response = api.post('/command', json={"name": name, "data": data})
    assert response.status_code == 200, response.text
    return response.json()


def verified(source):
    return Knowledge(title="Inspect", action="Inspect work", decision="Continue or hold", reason="Expert guidance",
                     rule="Ask when unsure", exception="Not established", guardrail="Hold when uncertain",
                     escalation="Ask the expert", evidence_ids=[source.id], status="verified")


def test_empty_first_launch_and_authorization(api):
    assert api.get('/state', headers={"Authorization": "Bearer wrong"}).status_code == 401
    state = api.get('/state').json()
    assert state['sessions'] == [] and state['session'] is None
    assert not state['credentials']['openai'] and not state['credentials']['elevenlabs']
    assert state['practice'] == {"items": [], "answers": {}}


def test_notes_persist_without_credentials_and_events_order(api):
    with api.websocket_connect('/events', headers={"Authorization": "Bearer test-token"}) as socket:
        assert socket.receive_json()['type'] == 'resync'
        command(api,'new', title='User-created workflow')
        first = socket.receive_json()
        command(api,'note',text='An expert-authored explanation')
        second = socket.receive_json()
        assert second['sequence'] > first['sequence']
        assert second['sessionId'] == first['sessionId']
        assert second['revision'] > first['revision']
    state = api.get('/state').json()
    sid = state['session']['id']
    command(api,'open',id=sid)
    assert api.get('/state').json()['session']['evidence'][0]['text'] == 'An expert-authored explanation'
    assert api.post('/command',json={"name":"build-map"}).status_code == 400


def test_pause_blocks_evidence_and_session_switch(api):
    command(api,'new',title='Private work')
    command(api,'recording',state='paused',duration=2)
    assert api.post('/command',json={"name":"note","data":{"text":"Not captured"}}).status_code == 400
    assert api.post('/command',json={"name":"new","data":{"title":"Other"}}).status_code == 400
    assert api.post('/frame',content=b'not-an-image').status_code == 200
    assert api.get('/state').json()['session']['evidence'] == []


def test_keys_never_appear_in_state_or_session(api,tmp_path):
    command(api,'credentials',openai_key='secret-value',eleven_key='other-secret')
    command(api,'new',title='Test')
    state = api.get('/state')
    assert state.json()['credentials']['openai']
    assert 'secret-value' not in state.text
    assert b'secret-value' not in (tmp_path/'apprentice.sqlite3').read_bytes()


def test_forget_removes_media_and_invalidates_map(api):
    command(api,'new',title='Recorded work')
    command(api,'note',text='Source')
    service=api.app.state.service
    source=service.session.evidence[0]
    source.image='evidence.jpg'
    service.repo.store.media(service.session.id,source.image).write_bytes(b'image')
    service.repo.store.media(service.session.id,'clip.webm').write_bytes(b'video')
    service.session.recordings=['clip.webm']
    service.session.knowledge=[verified(source)]
    service.session.confirmed=True
    command(api,'forget',id=source.id)
    state=api.get('/state').json()['session']
    assert not state['knowledge'] and not state['recordings'] and not state['confirmed']
    assert not service.repo.store.media(service.session.id,'clip.webm').exists()


def test_confirmation_requires_review_and_valid_sources(api):
    command(api,'new',title='Knowledge')
    command(api,'note',text='Confirmed expert explanation')
    service=api.app.state.service
    item=verified(service.session.evidence[0]);item.status='inferred'
    service.session.knowledge=[item]
    assert api.post('/command',json={"name":"confirm"}).status_code==400
    command(api,'edit-knowledge',id=item.id,patch={"status":"verified"})
    command(api,'confirm')
    assert api.get('/state').json()['session']['confirmed']
    command(api,'note',text='Additional expert context')
    assert not api.get('/state').json()['session']['confirmed']


def test_legacy_import_keeps_original_and_excludes_demo(api,tmp_path):
    legacy=tmp_path/'legacy'
    store=SessionStore(legacy)
    live=Session(title='Existing user workflow');demo=Session(title='Fixture',mode='demo')
    store.save(live);store.save(demo);store.close()
    response=api.post('/import',json={"path":str(legacy)})
    assert response.json()['count']==1
    assert [s['id'] for s in api.get('/state').json()['sessions']]==[live.id]
    assert api.post('/import',json={"path":str(legacy)}).json()['count']==0
    original=SessionStore(legacy)
    assert len(original.list())==2
    original.close()


def test_async_result_discarded_after_privacy_change(tmp_path):
    async def scenario():
        service=Service(tmp_path,Settings(openai_key='fixture'))
        await service.command('new',{'title':'Task','cloud':True})
        started=threading.Event();release=threading.Event();applied=[]
        def slow():
            started.set();release.wait(3);return 'stale result'
        await service.launch('test',slow,applied.append)
        await asyncio.to_thread(started.wait,1)
        await service.command('cloud',{'enabled':False})
        release.set()
        await asyncio.gather(*service.tasks)
        assert applied==[]
        await service.close()
    asyncio.run(scenario())


def test_training_rejects_unconfirmed_and_hallucinated_knowledge():
    class Fake:
        def request(self,*args):return Exercises(items=[Exercise(question='Unsupported?',knowledge_ids=['missing'])])
    source=Evidence(kind='note',text='Expert explanation')
    session=Session(title='Real task',evidence=[source],knowledge=[verified(source)])
    with pytest.raises(ValueError,match='Confirm'):generate(Fake(),session)
    session.confirmed=True
    with pytest.raises(ValueError,match='unsupported'):generate(Fake(),session)


def test_provider_failure_is_not_fabricated_or_leaked(tmp_path):
    async def scenario():
        service=Service(tmp_path,Settings(openai_key='fixture'));await service.command('new',{'title':'Task','cloud':True})
        queue=asyncio.Queue();service.listeners.add(queue)
        def fail():raise RuntimeError('secret-key and private request')
        await service.launch('test',fail,lambda result:None)
        await asyncio.gather(*service.tasks)
        events=[]
        while not queue.empty():events.append(queue.get_nowait())
        assert any(e['type']=='error' for e in events)
        assert 'secret-key' not in str(events)
        assert not service.session.messages
        await service.close()
    asyncio.run(scenario())


def test_complete_debrief_map_and_teaching_contract(api, monkeypatch):
    from apprentice.agents.gateway import Gateway
    from apprentice.domain import MapResult, DraftKnowledge, QuestionResult, TutorResult
    command(api, 'credentials', openai_key='fixture')
    command(api, 'new', title='Expert-created task', cloud=True)
    command(api, 'note', text='When a required approval is missing, hold the task and ask its owner.')
    service = api.app.state.service
    source = service.session.evidence[0]
    def response(self, schema, instructions, data, images=None):
        if schema is QuestionResult:
            return QuestionResult(question='Who owns that approval?', evidence_ids=[source.id])
        if schema is MapResult:
            return MapResult(items=[DraftKnowledge(title='Check approval', action='Check required approval',
                decision='Hold if missing', reason='Expert explanation', rule='Approval is required',
                exception='Not established', guardrail='Do not proceed without approval', escalation='Ask owner',
                evidence_ids=[source.id], check=None, needs_clarification=False)], teach_back='Hold and ask when approval is missing.', gaps=[])
        item = service.session.knowledge[0]
        if schema is Exercises:
            return Exercises(items=[Exercise(question='In a hypothetical task, approval is missing. What do you do?', knowledge_ids=[item.id])])
        if schema is TutorResult:
            return TutorResult(verdict='ok', explanation='Holding and asking follows the confirmed rule.', knowledge_ids=[item.id])
        raise AssertionError('Unexpected model schema')
    monkeypatch.setattr(Gateway, 'request', response)
    def wait_jobs():
        import time
        for _ in range(100):
            if not api.get('/state').json()['busy']:
                return
            time.sleep(.01)
        raise AssertionError('Job did not finish')
    command(api, 'debrief'); wait_jobs()
    assert api.get('/state').json()['question']['text'] == 'Who owns that approval?'
    command(api, 'note', kind='answer', text='The task owner.')
    command(api, 'build-map'); wait_jobs()
    item = api.get('/state').json()['session']['knowledge'][0]
    command(api, 'edit-knowledge', id=item['id'], patch={'status':'verified'})
    command(api, 'confirm')
    command(api, 'practice'); wait_jobs()
    assert len(api.get('/state').json()['practice']['items']) == 1
    command(api, 'tutor', index=0, text='Hold and ask the owner.'); wait_jobs()
    state = api.get('/state').json()
    assert state['practice']['answers']['0']['verdict'] == 'ok'
    assert state['session']['evidence'][-1]['kind'] == 'trainee_attempt'
    assert state['session']['confirmed']
    command(api, 'coaching', enabled=True)
    command(api, 'note', text='Trainee context')
    assert api.get('/state').json()['session']['evidence'][-1]['kind'] == 'trainee_note'


def test_headless_elevenlabs_audio_contract():
    import httpx
    from backend.voice import ElevenVoice
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.headers['xi-api-key']=='fixture'
        if request.url.path.endswith('speech-to-text'):
            assert b'audio/webm' in request.content
            return httpx.Response(200,json={'text':'Expert voice explanation'})
        return httpx.Response(200,content=b'mp3-fixture')
    voice=ElevenVoice(Settings(eleven_key='fixture'),httpx.MockTransport(respond))
    assert voice.speak('A question from evidence')==b'mp3-fixture'
    assert voice.transcribe(b'webm-fixture')=='Expert voice explanation'
    assert len(calls)==2
