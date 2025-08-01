# coding: utf-8
import secrets
import jwt
import requests

from logging import getLogger

from fastapi import status, HTTPException, Security  # noqa: F401
from fastapi.security import (  # noqa: F401
    HTTPAuthorizationCredentials,
    HTTPBearer,
    HTTPBasic,
    HTTPBasicCredentials,
)

from openapi_server.models.create_service_token_resp import CreateServiceTokenResp
from openapi_server.settings import GetSettings

from openapi_server.impl.scicat import get_scicat_api_prefix, get_scicat_endpoint

from starlette.status import HTTP_401_UNAUTHORIZED

bearer_security = HTTPBearer()

_LOGGER = getLogger("uvicorn.security")


async def get_token_BearerAuth(
    credentials: HTTPAuthorizationCredentials = Security(bearer_security),
):
    if not credentials:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )

    token = credentials.credentials
    payload = await validate_token(token)
    return payload


def get_keycloak_public_key():
    settings = GetSettings()
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


def get_public_key_from_jwks(kid, jwks):
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    return None


async def validate_token(token: str, fallback_validator=None) -> dict:
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
    settings = GetSettings()
    jwks = get_keycloak_public_key()
    if not jwks:
        detail = "Failed to retrieve JWKS from Keycloak"
        _LOGGER.error(detail)
        raise HTTPException(status_code=401, detail=detail)

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]
    except (jwt.DecodeError, KeyError):
        detail = "Failed to retrieve 'kid' (Key ID) from JWT."
        if not fallback_validator:
            _LOGGER.error(detail)
            raise HTTPException(status_code=401, detail=detail)

        # we assume we got a SciCat token, not a token from Keycloak
        if await fallback_validator(token):
            return {}, None
        else:
            detail = "Not a valid SciCat token"
            raise HTTPException(status_code=401, detail=detail)

    key_data = get_public_key_from_jwks(kid, jwks)
    if not key_data:
        detail = "Public key not found in JWKS for the provided kid"
        _LOGGER.error(detail)
        raise HTTPException(status_code=401, detail=detail)

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
    except jwt.ExpiredSignatureError:
        detail = "Token has expired"
        _LOGGER.warning(detail)
        raise HTTPException(status_code=401, detail=detail)

    except jwt.PyJWTError as e:
        detail = f"Failed to verify JWT: {str(e)}"
        _LOGGER.warning(detail)
        raise HTTPException(status_code=401, detail=detail)

    except jwt.InvalidTokenError as e:
        detail = f"Invalid token: {str(e)}"
        _LOGGER.warning(detail)
        raise HTTPException(status_code=401, detail=detail)


def generate_token() -> CreateServiceTokenResp:
    settings = GetSettings()
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
        detail = f"Error requesting test-token. Could not reach {settings.IDP_URL} because of timeout"
        _LOGGER.error(detail)
        raise HTTPException(status_code=500, detail=detail)
    except requests.exceptions.RequestException as e:
        detail = f"Error requesting test-token: {e}"
        _LOGGER.error(detail)
        raise HTTPException(status_code=500, detail=detail)

    if response.status_code == 200:
        _LOGGER.info("Successfully obtained access and refresh token")
        return CreateServiceTokenResp.from_dict(response.json())
    else:
        detail = f"Failed to get token: {response.status_code}, {response.text}"
        _LOGGER.error(detail)
        raise HTTPException(status_code=500, detail=detail)


async def get_token_SciCatAuth(
    credentials: HTTPAuthorizationCredentials = Security(bearer_security),
):
    if not credentials:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )
    token = credentials.credentials
    payload = await validate_token(token, check_scicat_token)
    return payload


async def get_scicat_user_info(token) -> dict:
    scicat_endpoint = await get_scicat_endpoint()
    scicat_api_prefix = await get_scicat_api_prefix()

    scicat_path = f"{scicat_endpoint}{scicat_api_prefix}"

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{scicat_path}/users/my/identity", headers=headers)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        detail = "Provided token is not a valid SciCat token"
        _LOGGER.error(detail)
        raise HTTPException(status_code=401, detail=detail) from e
    return response.json()


async def check_scicat_token(token) -> bool:
    scicat_userinfo = await get_scicat_user_info(token)
    try:
        groups = scicat_userinfo["profile"]["accessGroups"]
    except KeyError as e:
        detail = "Userinfo from SciCat does not contain the profile.accessGroups attribute"
        _LOGGER.error(detail)
        # return False
        raise HTTPException(status_code=401, detail=detail) from e

    if GetSettings().SCICAT_INGESTOR_GROUP not in groups:
        detail = "SciCat user does have ingestor role"
        _LOGGER.error(detail)
        # return False
        raise HTTPException(status_code=401, detail=detail)
    return True


basic_security = HTTPBasic()


def get_token_BasicAuth(credentials: HTTPBasicCredentials = Security(basic_security)):
    settings = GetSettings()
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = str.encode(settings.JOB_ENDPOINT_USERNAME.get_secret_value())
    is_correct_username = secrets.compare_digest(current_username_bytes, correct_username_bytes)
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = str.encode(settings.JOB_ENDPOINT_PASSWORD.get_secret_value())
    is_correct_password = secrets.compare_digest(current_password_bytes, correct_password_bytes)
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
