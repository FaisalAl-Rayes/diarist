import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from jwt.api_jws import encode

ISSUER = "https://clerk.example.test"
PARTY = "http://localhost:3000"


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def tokens(signing_key):
    def sign(changes=None, missing=(), *, key=None, algorithm="RS256", headers=None):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "user_a",
            "sid": "sess_a",
            "azp": PARTY,
            "iat": now - 5,
            "nbf": now - 5,
            "exp": now + 60,
        }
        claims.update(changes or {})
        for name in missing:
            claims.pop(name, None)
        return encode(
            json.dumps(claims).encode(),
            key or signing_key,
            algorithm=algorithm,
            headers={"kid": "test-key", **(headers or {})},
        )

    return sign


@pytest.fixture
def trusted_jwks(monkeypatch, signing_key):
    data = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwks = {"keys": [{**data, "kid": "test-key", "alg": "RS256", "use": "sig"}]}
    requests = []

    def fetch(client):
        requests.append(client.uri)
        return jwks

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fetch)
    return requests
