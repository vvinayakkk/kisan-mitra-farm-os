import pytest

from skyview.data.v3.ingestion import import_reviewed


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gov.uk.evil.example/info",
        "https://farmers.gov.evil.example/",
        "http://www.gov.uk/",
        "https://unreviewed.example/",
    ],
)
def test_reviewed_source_rejects_untrusted_or_insecure_host(url):
    with pytest.raises(ValueError, match="official HTTPS"):
        import_reviewed(None, {"source_url": url})


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gov.uk/",
        "https://www.farmers.gov/",
        "https://agritech.tnau.ac.in/",
        "https://agriculture.ec.europa.eu/",
        "https://www.pib.gov.in/",
    ],
)
def test_official_sources_still_require_review_evidence(url):
    with pytest.raises(ValueError, match="reviewed_by and evidence_text"):
        import_reviewed(None, {"source_url": url})


def test_essential_solar_credit_soil_irrigation_references_are_actionable_not_entitlements():
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2] / "data_platform/v3/catalog/reviewed_sources.json"
    )
    document = json.loads(path.read_text())
    schemes = {
        s["scheme_code"]: s for b in document["bundles"] for s in b.get("schemes", [])
    }
    for code in ("PM-KUSUM", "KCC", "SOIL-HEALTH-CARD", "PMKSY-HKKP"):
        scheme = schemes[code]
        assert scheme["requirements"]["decision"] == "official_authority_only"
        assert scheme["requirements"]["questions"]
        assert (
            scheme["requirements"]["application_status"]
            == "verify_current_state_or_bank_notice"
        )
        assert scheme["application_url"].startswith("https://")
        assert "valid_to" not in scheme  # No invented current deadline.
    assert "repayable credit" in schemes["KCC"]["requirements"]["summary"]
    assert "open application window" in schemes["PM-KUSUM"]["requirements"]["summary"]
