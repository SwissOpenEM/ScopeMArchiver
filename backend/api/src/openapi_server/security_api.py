# coding: utf-8
import jwt
import requests

from typing import List
from logging import getLogger

from fastapi import Depends, HTTPException, Security  # noqa: F401
from fastapi.security import (  # noqa: F401
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from openapi_server.settings import Settings

from starlette.status import HTTP_401_UNAUTHORIZED
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, Security

security = HTTPBearer()
settings = Settings()
_LOGGER = getLogger("api.security")


def get_token_BearerAuth(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    if not credentials:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )

    token = credentials.credentials
    payload = validate_token(token)
    return payload


def get_keycloak_public_key():
    try:
        response = requests.get(
            f"{settings.IDP_URL}/realms/{settings.IDP_REALM}/protocol/openid-connect/certs"
        )
        response.raise_for_status()
        jwks = response.json()
        return jwks
    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"Error fetching public keys from Keycloak: {e}")
        return None


def get_jwk_from_token(token):
    try:
        # Decode JWT header to get 'kid' (Key ID) which identifies which public key to use
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header is None:
            raise Exception("Token is not a valid JWT")
        return unverified_header["kid"]
    except jwt.PyJWTError as e:
        _LOGGER.error(f"Error decoding JWT header: {e}")
        return None


def get_public_key_from_jwks(kid, jwks):
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    return None


def validate_token(token: str) -> dict:
    """
    Validates a JWT Bearer token.

    Args:
        token (str): The Bearer token string.

    Returns:
        dict: Decoded payload if the token is valid.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    # TODO: we might cache the jwks at some point, as this information does not change often
    jwks = get_keycloak_public_key()
    if not jwks:
        raise HTTPException(
            status_code=401,
            detail="Failed to retrieve JWKS",
        )

    kid = get_jwk_from_token(token)
    if not kid:
        raise HTTPException(
            status_code=401,
            detail="Failed to extract Key ID (kid) from JWT",
        )

    key_data = get_public_key_from_jwks(kid, jwks)
    if not key_data:
        raise HTTPException(
            status_code=401,
            detail="Public key not found in JWKS for the provided kid",
        )

    try:
        # Verify the JWT using the public key from JWKS
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=[settings.IDP_ALGORITHM],
            audience=settings.IDP_AUDIENCE,
            issuer=f"{settings.IDP_URL}/realms/{settings.IDP_REALM}",
        )
        return decoded_token, None  # Successfully decoded
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Failed to verify JWT: {str(e)}")

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token validation error: {str(e)}",
        )


def generate_token() -> dict:
    # Token request payload
    payload = {
        "client_id": settings.IDP_CLIENT_ID,
        "client_secret": settings.IDP_CLIENT_SECRET.get_secret_value(),
        "grant_type": "password",
        "username": settings.IDP_USERNAME,
        "password": settings.IDP_PASSWORD.get_secret_value(),
    }

    # Make the request to obtain a token
    try:
        response = requests.post(
            f"{settings.IDP_URL}/realms/{settings.IDP_REALM}/protocol/openid-connect/token",
            data=payload,
            timeout=5,
        )
    except requests.exceptions.Timeout:
        _LOGGER.error(
            f"Error requesting test-token. Could not reach {settings.IDP_URL} because of timeout"
        )
        return
    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"Error requesting test-token: {e}")
        return

    if response.status_code == 200:
        _LOGGER.info("Successfully obtained access and refresh token")
        return response.json()
    else:
        _LOGGER.error("Failed to get token:", response.status_code, response.text)
