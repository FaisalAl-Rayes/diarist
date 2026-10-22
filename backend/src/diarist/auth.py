"""Clerk session verification, independent of job persistence and ownership."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

import jwt
from fastapi import Header, HTTPException


class AuthConfigurationError(ValueError):
    pass


def _is_origin(value: str, *, https_only: bool = False) -> bool:
    try:
        url = urlsplit(value)
        return bool(
            url.scheme in (("https",) if https_only else ("https", "http"))
            and url.hostname
            and url.port != 0
            and not url.username
            and not url.password
            and not url.path
            and not url.query
            and not url.fragment
            and "*" not in value
            and not any(char.isspace() for char in value)
        )
    except ValueError:
        return False


class ClerkVerifier:
    def __init__(self, issuer: str, authorized_parties: tuple[str, ...]) -> None:
        if (
            not _is_origin(issuer, https_only=True)
            or not authorized_parties
            or not all(_is_origin(party) for party in authorized_parties)
        ):
            raise AuthConfigurationError("Clerk issuer and authorized parties must be configured")
        self.issuer = issuer
        self.authorized_parties = authorized_parties
        self.jwks = jwt.PyJWKClient(issuer + "/.well-known/jwks.json", timeout=5)

    def verify(self, token: str) -> str:
        # Only kid selects a key, always from our configured issuer. Never use
        # token-provided iss/jku/x5u URLs as network destinations.
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise jwt.InvalidTokenError("Invalid signing header")
        key = self.jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=self.issuer,
            options={
                "require": ["exp", "nbf", "iat", "iss", "sub", "sid", "azp"],
                "verify_aud": False,  # Ordinary Clerk session tokens have no app audience.
            },
        )
        if any(type(claims[name]) is not int for name in ("exp", "nbf", "iat")):
            raise jwt.InvalidTokenError("Invalid session timestamps")
        if any(
            not isinstance(claims[name], str) or not claims[name].strip()
            for name in ("sub", "sid", "azp")
        ):
            raise jwt.InvalidTokenError("Invalid session identity")
        if claims["azp"] not in self.authorized_parties:
            raise jwt.InvalidTokenError("Invalid authorized party")
        if "sts" in claims and claims["sts"] != "active":
            raise jwt.InvalidTokenError("Invalid session status")
        return claims["sub"]


@lru_cache(maxsize=1)
def get_verifier() -> ClerkVerifier:
    return ClerkVerifier(
        os.getenv("CLERK_ISSUER_URL", ""),
        tuple(
            party.strip()
            for party in os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",")
            if party.strip()
        ),
    )


def authenticated_user(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        raise HTTPException(401, "Invalid session", headers={"WWW-Authenticate": "Bearer"})
    try:
        return get_verifier().verify(token)
    except (AuthConfigurationError, jwt.PyJWKClientConnectionError) as exc:
        raise HTTPException(503, "Authentication unavailable") from exc
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}) from exc
