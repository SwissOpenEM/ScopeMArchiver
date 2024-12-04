
import base64
from typing import List

from fastapi.responses import JSONResponse
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.internal_error import InternalError
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp

from openapi_server.apis.presigned_urls_api_base import BasePresignedUrlsApi
from openapi_server.settings import Settings

from .s3 import complete_multipart_upload, abort_multipart_upload, create_presigned_url, create_presigned_urls_multipart

from logging import getLogger

_LOGGER = getLogger("api.presignedurls")

_SETTINGS = Settings()


class BasePresignedUrlsApiImpl(BasePresignedUrlsApi):

    async def complete_upload(  # type: ignore
        self,
        complete_upload_body: CompleteUploadBody,
    ) -> CompleteUploadResp:
        try:
            return complete_multipart_upload(_SETTINGS.MINIO_LANDINGZONE_BUCKET, complete_upload_body)
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(status_code=500, content={"message": "Failed to complete upload", "details": str(e)})

    async def abort_multipart_upload(
        self,
        abort_upload_body: AbortUploadBody,
    ) -> object:
        try:
            resp = abort_multipart_upload(bucket_name=_SETTINGS.MINIO_LANDINGZONE_BUCKET,
                                          object_name=abort_upload_body.object_name,
                                          upload_id=abort_upload_body.upload_id)
            return {}
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(status_code=500, content={"message": "Failed to abort multipart upload", "details": str(e)})

    async def get_presigned_urls(
        self,
        presigned_url_body: PresignedUrlBody,
    ) -> PresignedUrlResp:
        try:
            if presigned_url_body.parts == 1:
                url = create_presigned_url(bucket_name=_SETTINGS.MINIO_LANDINGZONE_BUCKET,
                                           object_name=presigned_url_body.object_name)
                b64url = base64.b64encode(url.encode("utf-8")).decode()
                _LOGGER.debug("Presigned Url created: %s", url)
                return PresignedUrlResp(UploadID="", Urls=[b64url])
            else:

                uploadId, urls = create_presigned_urls_multipart(bucket_name=_SETTINGS.MINIO_LANDINGZONE_BUCKET,
                                                                 object_name=presigned_url_body.object_name,
                                                                 part_count=presigned_url_body.parts)
                b64urls: List[str] = [base64.b64encode(b[1].encode("utf-8")).decode() for b in urls]
                _LOGGER.debug("Presigned Urls created: %s", urls)
                return PresignedUrlResp(UploadID=uploadId, Urls=b64urls)
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(status_code=500, content={"message": "Failed to get presigned urls", "details": str(e)})
