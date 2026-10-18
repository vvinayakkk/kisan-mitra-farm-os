from contextlib import nullcontext

from skyview.data.v3 import repository


def test_missing_explicit_station_does_not_substitute_reference(monkeypatch):
    monkeypatch.setattr(repository, 'connection', lambda owner: nullcontext(None))
    monkeypatch.setattr(repository, '_station', lambda *args: None)
    monkeypatch.setattr(repository, 'rows', lambda *args: (_ for _ in ()).throw(AssertionError('must not read reference')))
    assert repository.station_snapshot('owner', 'private-station')['available'] is False
    assert repository.weather_history('owner', 'private-station')['data'] == []


def test_default_station_history_uses_restricted_reference_function(monkeypatch):
    monkeypatch.setattr(repository, 'connection', lambda owner: nullcontext(None))
    monkeypatch.setattr(repository, '_station', lambda *args: None)
    queries = []
    def read(db, sql, args):
        queries.append((sql, args))
        return [{'record': {'reference': True, 'observed_at': '2026-10-18T00:00:00Z'}}]
    monkeypatch.setattr(repository, 'rows', read)
    result = repository.weather_history('owner', limit=9999)
    assert result['reference'] is True
    assert result['totalRecords'] == 1
    assert queries == [('SELECT sv3.station_reference_packets(:limit) AS record', {'limit': 2000})]
