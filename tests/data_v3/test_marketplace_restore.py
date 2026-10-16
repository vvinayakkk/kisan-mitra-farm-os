"""Resource matching uses shared catalog values and makes no deal/contact claims."""

import importlib.util
from pathlib import Path

from skyview.api import v3_routes


def farmer(identifier, excess, required):
    return {
        "id": identifier,
        "name": identifier,
        "latitude": 16.5,
        "longitude": 80.6,
        "excess_resources": excess,
        "required_resources": required,
        "data_origin": "synthetic",
        "exchange_listings": [{"id": identifier + "-notice", "title": excess[0]}],
    }


def test_compatibility_matches_and_three_way_barter_share_notice_catalog(monkeypatch):
    own = farmer("a", ["Tractor"], ["Sprayer", "Harvesting labour"])
    others = [
        farmer("b", ["Sprayer"], ["Harvesting labour", "Farm transport"]),
        farmer("c", ["Harvesting labour"], ["Farm transport", "Tractor"]),
        farmer("d", ["Farm transport"], ["Tractor", "Sprayer"]),
    ]
    monkeypatch.setattr(v3_routes.repo, "profile", lambda owner: {"profile": own})
    monkeypatch.setattr(
        v3_routes.repo, "directory", lambda: {"farmers": [own] + others}
    )
    result = v3_routes.matches(v3_routes.MatchRequest(), "a")
    assert {match["id"] for match in result["matches"]} == {"b", "c", "d"}
    assert all(
        match["agreements_executed"] is False and match["exchange_listings"]
        for match in result["matches"]
    )
    assert all(
        match["distance_kind"] == "approximate_straight_line"
        for match in result["matches"]
    )
    loops = v3_routes.loops("a", v3_routes.MatchRequest())
    assert loops["count"] > 0
    assert all(
        loop["agreements_executed"] is False and len(loop["trades"]) == 3
        for loop in loops["loops"]
    )


def test_demo_seed_is_guarded_stable_and_never_fabricates_conversation(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "data_platform/v3")
    )
    spec = importlib.util.spec_from_file_location(
        "seed_exchange_demo_test",
        Path(__file__).resolve().parents[2] / "data_platform/v3/seed_exchange_demo.py",
    )
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    profile = {
        "id": "00000000-0000-0000-0000-000000000001",
        "display_name": "Demo farmer 0001",
        "state": "Andhra Pradesh",
        "district": None,
    }
    statements = seed.statements([profile])
    assert "current_database()<>'skyview_v3_demo'" in statements
    assert statements.count("INSERT INTO sv3.exchange_listings") == 3
    assert (
        "exchange_messages" not in statements
        and "exchange_conversations" not in statements
    )
    assert "DELETE " not in statements
    assert "Sample resource listing." in statements
    assert statements == seed.statements([profile])
    assert "Farmer 0001" in statements
    assert seed.literal("O'Brien") == "'O''Brien'"


def test_barter_matches_require_the_candidate_to_actually_offer_resource(monkeypatch):
    from contextlib import contextmanager

    from skyview.api import v3_exchange_routes as exchange

    class Connection:
        def execute(self, *args):
            return self

        def scalar(self):
            return False

    @contextmanager
    def scope(*args):
        yield Connection()

    common = {
        "status": "published",
        "state": "Andhra Pradesh",
        "district": "Guntur",
        "available_on": None,
        "category": "equipment",
    }
    source = {
        **common,
        "id": "source",
        "title": "Tractor",
        "kind": "offer",
        "exchange_for": "Sprayer",
    }
    candidates = [
        {
            **common,
            "id": "real-offer",
            "title": "Sprayer",
            "kind": "offer",
            "exchange_for": "Tractor",
        },
        {
            **common,
            "id": "request-only",
            "title": "Sprayer",
            "kind": "request",
            "exchange_for": "Tractor",
        },
        {
            **common,
            "id": "direct-request",
            "title": "Tractor",
            "kind": "request",
            "exchange_for": "",
        },
    ]
    monkeypatch.setattr(exchange, "connection_scope", scope)
    monkeypatch.setattr(exchange, "one", lambda *args: source)
    monkeypatch.setattr(exchange, "rows", lambda *args: candidates)
    result = exchange.matches("source", "owner")
    assert {item["id"] for item in result["items"]} == {"real-offer", "direct-request"}


def test_three_marketplace_match_classes_and_resource_coverage(monkeypatch):
    own = farmer("owner", ["Tractor"], ["Sprayer"])
    candidates = [
        farmer("mutual", ["Sprayer"], ["Tractor"]),
        farmer("provider", ["Sprayer"], ["Harvesting labour"]),
        farmer("consumer", ["Farm transport"], ["Tractor"]),
        farmer("unrelated", ["Farm transport"], ["Harvesting labour"]),
    ]
    monkeypatch.setattr(v3_routes.repo, "profile", lambda owner: {"profile": own})
    monkeypatch.setattr(v3_routes.repo, "directory", lambda: {"farmers": candidates})
    matches = v3_routes.matches(v3_routes.MatchRequest(), "owner")["matches"]
    by_id = {item["id"]: item for item in matches}
    assert set(by_id) == {"mutual", "provider", "consumer"}
    assert matches[0]["id"] == "mutual"
    assert (
        by_id["mutual"]["is_mutual"]
        and by_id["mutual"]["is_provider"]
        and by_id["mutual"]["is_consumer"]
    )
    assert by_id["mutual"]["match_percentage"] == 100
    assert (
        by_id["provider"]["match_type"] == "provider"
        and by_id["provider"]["is_provider"]
        and not by_id["provider"]["is_consumer"]
    )
    assert (
        by_id["consumer"]["match_type"] == "consumer"
        and by_id["consumer"]["is_consumer"]
        and not by_id["consumer"]["is_provider"]
    )
    assert by_id["consumer"]["i_provide_they_need"] == ["Tractor"]
    assert by_id["provider"]["they_provide_i_need"] == ["Sprayer"]
    assert (
        by_id["provider"]["match_percentage"]
        == by_id["consumer"]["match_percentage"]
        == 50
    )
    assert all("not trust" in item["match_percentage_basis"] for item in matches)
