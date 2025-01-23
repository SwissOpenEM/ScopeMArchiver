# coding: utf-8
import jwt

from typing import List

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
    try:
        # Decode the JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iss", "aud"]},  # Ensure these claims exist
            issuer=settings.ISSUER,  # Verify the token's issuer
            audience=settings.AUDIENCE,  # Verify the token's audience
        )
        return payload

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
