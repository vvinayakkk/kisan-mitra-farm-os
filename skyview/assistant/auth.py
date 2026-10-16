"""OIDC bearer verification for live bootstrap; never trust browser farmer IDs."""

import hashlib
import os
import threading
import time
from urllib.parse import urlparse

import httpx
import jwt
from sqlalchemy import text

from skyview.data.v3 import db as database

_cache = {}
_lock = threading.Lock()


class AuthenticationUnavailable(ValueError):
    pass


def _jwks(url):
    with _lock:
        cached = _cache.get(url)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        response = httpx.get(url, timeout=4, follow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 128000:
            raise ValueError("JWKS response exceeds limit")
        payload = response.json()
        keys = payload.get("keys", [])
        if not isinstance(keys, list) or len(keys) > 50:
            raise ValueError("Invalid JWKS")
        _cache[url] = (time.monotonic() + 300, keys)
        return keys


def verify_identity(token):
    url = os.getenv("V3_AUTH_JWKS_URL", "")
    issuer = os.getenv("V3_AUTH_ISSUER", "")
    audience = os.getenv("V3_AUTH_AUDIENCE", "")
    if not all((url, issuer, audience)):
        raise AuthenticationUnavailable("Live sign-in provider is not configured")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise AuthenticationUnavailable("Sign-in JWKS endpoint must use HTTPS")
    if not token or len(token) > 16000:
        raise ValueError("Invalid sign-in token")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError("Unsupported sign-in signature")
        keys = _jwks(url)
        candidates = [
            key
            for key in keys
            if key.get("kid") == header["kid"]
            and key.get("kty") == "RSA"
            and key.get("use", "sig") == "sig"
            and key.get("alg", "RS256") == "RS256"
        ]
        if len(candidates) != 1:
            raise ValueError("Unknown sign-in key")
        key = jwt.PyJWK.from_dict(candidates[0], algorithm="RS256").key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            leeway=20,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 256:
            raise ValueError("Invalid account identity")
        return {
            "auth_subject": "oidc:"
            + hashlib.sha256((issuer + "\0" + subject).encode()).hexdigest(),
            "issuer": issuer,
        }
    except (jwt.PyJWTError, httpx.HTTPError, KeyError, TypeError) as exc:
        raise ValueError("Sign-in could not be verified") from exc


def create_live_session(token):
    identity = verify_identity(token)
    with database.connection(write=True) as db:
        fid = db.execute(
            text("SELECT sv3.assistant_oidc_farmer(:subject,:issuer)"),
            {"subject": identity["auth_subject"], "issuer": identity["issuer"]},
        ).scalar_one()
    from .v3_store import create_session_for_farmer

    return create_session_for_farmer(fid)
