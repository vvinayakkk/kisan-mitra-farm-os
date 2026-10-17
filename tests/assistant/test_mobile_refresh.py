"""Mobile custom answers keep question validation and owner-scoped history."""
from contextlib import contextmanager
import uuid
import pytest
from skyview.assistant import engine, v3_store


def test_select_question_accepts_farmer_words_but_bounds_input():
    pending = {"arguments": {"fields": [{"id": "water", "type": "select", "options": ["Rainfed", "Drip"]}]}}
    assert engine.validate_answers(pending, {"water": "A shared well with my neighbour"}) == {"water": "A shared well with my neighbour"}
    with pytest.raises(ValueError):
        engine.validate_answers(pending, {"water": "x" * 501})
    with pytest.raises(ValueError):
        engine.validate_answers(pending, {})


def test_history_queries_use_verified_owner_not_old_device_session(monkeypatch):
    owner = str(uuid.uuid4())
    seen = []
    class Result:
        def mappings(self): return []
        def scalar_one_or_none(self): return None
    class DB:
        def execute(self, sql, params):
            seen.append((str(sql), params))
            return Result()
    @contextmanager
    def connection(fid):
        assert fid == owner
        yield DB()
    monkeypatch.setattr(v3_store, 'farmer_id', lambda sid: owner)
    monkeypatch.setattr(v3_store.database, 'connection', connection)
    assert v3_store.conversations('new-device') == []
    assert v3_store.conversation('new-device', uuid.uuid4().hex) is None
    assert all('farmer_id=:fid' in sql and params['fid'] == owner for sql, params in seen)


def test_starter_plans_require_review_and_are_owner_scoped(monkeypatch):
    import json
    from pydantic import ValidationError
    from skyview.api import v3_onboarding_routes as routes
    with pytest.raises(ValidationError):
        routes.StarterPlanReview(approved=False)
    seen, owners = [], []
    @contextmanager
    def connection(owner, write=False):
        assert write
        owners.append(owner)
        yield object()
    monkeypatch.setattr(routes.db, 'connection', connection)
    monkeypatch.setattr(routes, 'onboarded', lambda conn, owner: None)
    monkeypatch.setattr(routes, 'sql', lambda conn, statement, **params: seen.append((statement, params)))
    owner = str(uuid.uuid4())
    first = routes.starter_plans(routes.StarterPlanReview(approved=True), owner)
    repeat = routes.starter_plans(routes.StarterPlanReview(approved=True), owner)
    other = routes.starter_plans(routes.StarterPlanReview(approved=True), str(uuid.uuid4()))
    assert first == repeat
    assert set(first['mission_ids']).isdisjoint(other['mission_ids'])
    assert len(first['mission_ids']) == 3
    for statement, params in seen:
        assert 'ON CONFLICT(id) DO NOTHING' in statement
        assert params['owner'] in owners
        assert all(not step['done'] for step in json.loads(params['steps']))
