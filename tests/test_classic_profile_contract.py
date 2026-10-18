import json
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skyview.api import v3_routes as routes


def client(monkeypatch):
    calls=[]
    class Connection:
        def execute(self, statement, args):
            calls.append((str(statement),args))
            return self
        def scalar(self):
            return 'state-id' if calls[-1][1]['name']=='Andhra Pradesh' else None
    @contextmanager
    def connection(owner,write=False):
        assert owner=='owned-farmer' and write
        yield Connection()
    monkeypatch.setattr(routes.db,'connection',connection)
    monkeypatch.setattr(routes.repo,'profile',lambda owner:{'profile':{'id':owner}})
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.identity]=lambda:'owned-farmer'
    return TestClient(app),calls


def test_classic_fields_are_saved_for_authenticated_owner(monkeypatch):
    http,calls=client(monkeypatch)
    response=http.post('/api/profile/save',json={'name':'Farmer','state':'Andhra Pradesh','latitude':0,'longitude':78,'whatsapp_number':'+919999999999','crops':'Maize, Rice','phone':'another-person'})
    assert response.status_code==200
    update=next(args for sql,args in calls if 'profile_attributes' in sql)
    attrs=json.loads(update['attrs'])
    assert attrs['latitude']==0 and attrs['longitude']==78
    assert attrs['whatsapp_number']=='+919999999999'
    assert attrs['crops']==['Maize','Rice']
    assert update['owner']=='owned-farmer' and 'phone' not in attrs
    assert any('region_id=:region' in sql for sql,args in calls)


def test_invalid_state_or_partial_coordinates_do_not_succeed(monkeypatch):
    http,calls=client(monkeypatch)
    assert http.post('/api/profile/save',json={'state':'Invalid place'}).status_code==422
    assert not any('UPDATE' in sql for sql,args in calls)
    assert http.post('/api/profile/save',json={'latitude':20}).status_code==422
    assert http.post('/api/profile/save',json={'latitude':100,'longitude':78}).status_code==422
