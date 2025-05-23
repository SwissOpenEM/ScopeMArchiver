from pydantic import SecretStr
import urllib

from httpx import AsyncClient

from prefect.blocks.system import Secret
from prefect.variables import Variable

SCICAT_DATASET_PATH = "/datasets"
SCICAT_JOB_PATH = "/jobs"
SCICAT_LOGIN_PATH = "/auth/login"


async def get_scicat_credentials():
    user_block = await Secret.load("scicat-user")
    password_block = await Secret.load("scicat-password")
    return SecretStr(user_block.get()), SecretStr(password_block.get())


async def get_scicat_token(
    scicat_endpoint: str, sciat_api_prefix: str, user: SecretStr, password: SecretStr
) -> SecretStr:
    async with AsyncClient() as client:
        resp = await client.post(
            url=f"{scicat_endpoint}{sciat_api_prefix}{SCICAT_LOGIN_PATH}",
            data={
                "username": f"{user.get_secret_value()}",
                "password": f"{password.get_secret_value()}",
            },
        )

        resp.raise_for_status()

        return SecretStr(resp.json()["access_token"])


async def get_scicat_endpoint():
    return await Variable.get("scicat_endpoint")


async def get_scicat_api_prefix():
    return await Variable.get("scicat_api_prefix")


def build_headers(token: SecretStr) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.get_secret_value()}",
        "Content-Type": "application/json",
    }


def safe_dataset_id(dataset_id: str):
    return urllib.parse.quote(dataset_id, safe="", encoding=None, errors=None)


async def mark_dataset_as_archivable(dataset_id: str):
    user, password = await get_scicat_credentials()

    endpoint = await get_scicat_endpoint()
    api_prefix = await get_scicat_api_prefix()

    token = await get_scicat_token(endpoint, api_prefix, user, password)
    data = {
        "datasetlifecycle": {
            "archiveStatusMessage": "datasetCreated",
            "archivable": True,
        }
    }

    headers = build_headers(token)
    pid = safe_dataset_id(dataset_id)
    async with AsyncClient() as client:
        response = await client.patch(
            url=f"{endpoint}{api_prefix}{SCICAT_DATASET_PATH}/{pid}",
            json=data,
            headers=headers,
        )

        response.raise_for_status()


async def start_archiving(owner_user: str, contact_email, owner_group: str, dataset_pid: str):
    user, password = await get_scicat_credentials()

    endpoint = await get_scicat_endpoint()
    api_prefix = await get_scicat_api_prefix()

    token = await get_scicat_token(endpoint, api_prefix, user, password)
    data = {
        "type": "archive",
        "jobParams": {
            "username": f"{owner_user}",
            "datasetList": [{"pid": f"{dataset_pid}", "files": []}],
        },
        "ownerUser": f"{owner_user}",
        "ownerGroup": f"{owner_group}",
        "contactEmail": f"{contact_email}",
    }

    headers = build_headers(token)

    async with AsyncClient() as client:
        response = await client.post(
            url=f"{endpoint}/api/v4{SCICAT_JOB_PATH}",
            json=data,
            headers=headers,
        )

        response.raise_for_status()
