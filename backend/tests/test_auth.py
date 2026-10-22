import importlib
import importlib.util
import time

import jwt
import pytest
from conftest import ISSUER, PARTY
from cryptography.hazmat.primitives.asymmetric import rsa


def test_valid_session_uses_only_configured_jwks(tokens, trusted_jwks):
    assert importlib.util.find_spec("diarist.auth") is not None, "Missing Clerk auth adapter"
    auth = importlib.import_module("diarist.auth")
    verifier = auth.ClerkVerifier(ISSUER, (PARTY,))
    assert verifier.verify(tokens(headers={"jku": "https://evil.example/keys"})) == "user_a"
    assert trusted_jwks == [ISSUER + "/.well-known/jwks.json"]


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"nbf": 4102444800},
        {"iat": 4102444800},
        {"iss": "https://attacker.example"},
        {"iss": [ISSUER]},
        {"sub": ""},
        {"sub": " "},
        {"sub": 123},
        {"sid": ""},
        {"sid": " "},
        {"sid": 123},
        {"azp": "https://attacker.example"},
        {"azp": [PARTY]},
        {"azp": ""},
        {"iat": str(int(time.time()) - 10)},
        {"nbf": False},
        {"iat": []},
        {"nbf": {}},
        {"exp": float("inf")},
        {"exp": str(int(time.time()) + 60)},
    ],
)
def test_invalid_signed_session_claims_rejected(tokens, trusted_jwks, changes):
    from diarist.auth import ClerkVerifier

    with pytest.raises(jwt.InvalidTokenError):
        ClerkVerifier(ISSUER, (PARTY,)).verify(tokens(changes))


@pytest.mark.parametrize("status", ["pending", "", "inactive", "ACTIVE", None, False, 1, [], {}])
def test_non_active_signed_session_status_rejected(tokens, trusted_jwks, status):
    from diarist.auth import ClerkVerifier

    with pytest.raises(jwt.InvalidTokenError):
        ClerkVerifier(ISSUER, (PARTY,)).verify(tokens({"sts": status}))


@pytest.mark.parametrize("changes", [{}, {"sts": "active"}])
def test_active_or_omitted_session_status_accepted(tokens, trusted_jwks, changes):
    from diarist.auth import ClerkVerifier

    assert ClerkVerifier(ISSUER, (PARTY,)).verify(tokens(changes)) == "user_a"


@pytest.mark.parametrize("claim", ["exp", "nbf", "iat", "iss", "sub", "sid", "azp"])
def test_all_session_claims_are_required(tokens, trusted_jwks, claim):
    from diarist.auth import ClerkVerifier

    with pytest.raises(jwt.InvalidTokenError):
        ClerkVerifier(ISSUER, (PARTY,)).verify(tokens(missing=(claim,)))


def test_bad_signature_algorithm_and_unknown_key_rejected(tokens, trusted_jwks):
    from diarist.auth import ClerkVerifier

    verifier = ClerkVerifier(ISSUER, (PARTY,))
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in [
        tokens(key=other_key),
        tokens(key="x" * 64, algorithm="HS256"),
        tokens(headers={"kid": "unknown"}),
        "invalid",
    ]:
        with pytest.raises(jwt.PyJWTError):
            verifier.verify(token)


@pytest.mark.parametrize(
    "issuer,parties",
    [
        ("", (PARTY,)),
        (ISSUER, ()),
        ("http://example.com", (PARTY,)),
        (ISSUER + "?other=1", (PARTY,)),
        ("https://user@example.com", (PARTY,)),
        (ISSUER, ("*",)),
        (ISSUER, (PARTY + "/path",)),
    ],
)
def test_missing_or_unsafe_config_fails_closed(issuer, parties):
    from diarist.auth import AuthConfigurationError, ClerkVerifier

    with pytest.raises(AuthConfigurationError):
        ClerkVerifier(issuer, parties)
