"""Real RSA signature verification with generated test identities; no remote keys."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from skyview.assistant import auth


@pytest.fixture
def signer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="fixture-rsa", use="sig", alg="RS256")
    monkeypatch.setenv("V3_AUTH_JWKS_URL", "https://login.example.invalid/keys")
    monkeypatch.setenv("V3_AUTH_ISSUER", "https://login.example.invalid/")
    monkeypatch.setenv("V3_AUTH_AUDIENCE", "skyview-fixture")
    monkeypatch.setattr(auth, "_jwks", lambda url: [jwk])

    def token(**changes):
        claims = {
            "sub": "fixture-farmer",
            "iss": "https://login.example.invalid/",
            "aud": "skyview-fixture",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            **changes,
        }
        return jwt.encode(
            claims, key, algorithm="RS256", headers={"kid": "fixture-rsa"}
        )

    return token


def test_verified_subject_is_stable_issuer_bound_and_not_client_farmer_id(signer):
    identity = auth.verify_identity(signer(farmer_id="attacker-supplied-id"))
    assert identity["auth_subject"].startswith("oidc:")
    assert identity == auth.verify_identity(signer())
    assert set(identity) == {"auth_subject", "issuer"}


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://wrong.example.invalid/"},
        {"aud": "another-app"},
        {"exp": int(time.time()) - 120},
        {"sub": ""},
        {"iat": int(time.time()) + 120},
    ],
)
def test_invalid_signed_claims_fail_closed(signer, changes):
    with pytest.raises(ValueError):
        auth.verify_identity(signer(**changes))


def test_unsigned_and_malformed_tokens_rejected(signer):
    with pytest.raises(ValueError):
        auth.verify_identity("not-a-jwt")
    unsigned = jwt.encode(
        {"sub": "attacker"}, key="", algorithm="none", headers={"kid": "fixture-rsa"}
    )
    with pytest.raises(ValueError):
        auth.verify_identity(unsigned)


def test_unconfigured_identity_is_explicitly_unavailable(monkeypatch):
    monkeypatch.delenv("V3_AUTH_JWKS_URL", raising=False)
    with pytest.raises(auth.AuthenticationUnavailable):
        auth.verify_identity("placeholder")


def test_firebase_phone_identity_is_verified_and_stable(monkeypatch):
    from firebase_admin import auth as firebase_auth

    monkeypatch.setenv("FIREBASE_PROJECT_ID", "farm-project")
    monkeypatch.setattr(firebase_auth, "verify_id_token", lambda token: {
        "uid": "farmer-123",
        "firebase": {"sign_in_provider": "phone"},
    })
    identity = auth.verify_identity("signed-token")
    assert identity == auth.verify_identity("signed-token")
    assert identity["issuer"] == "https://securetoken.google.com/farm-project"
    assert identity["auth_subject"].startswith("oidc:")


def test_firebase_rejects_non_phone_sign_in(monkeypatch):
    from firebase_admin import auth as firebase_auth

    monkeypatch.setenv("FIREBASE_PROJECT_ID", "farm-project")
    monkeypatch.setattr(firebase_auth, "verify_id_token", lambda token: {
        "uid": "farmer-123",
        "firebase": {"sign_in_provider": "anonymous"},
    })
    with pytest.raises(ValueError):
        auth.verify_identity("signed-token")
