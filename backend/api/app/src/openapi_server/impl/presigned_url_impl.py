
import base64
from typing import List

from fastapi.responses import JSONResponse
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp

from openapi_server.apis.presigned_urls_api_base import BasePresignedUrlsApi
from openapi_server.settings import Settings

from .s3 import complete_multipart_upload, abort_multipart_upload, create_presigned_url, create_presigned_urls_multipart
_SETTINGS = Settings()


class BasePresignedUrlsApiImpl(BasePresignedUrlsApi):

    async def complete_upload(  # type: ignore
        self,
        complete_upload_body: CompleteUploadBody,
    ) -> CompleteUploadResp:
        try:
            return complete_multipart_upload(_SETTINGS.MINIO_LANDINGZONE_BUCKET, complete_upload_body)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

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
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def get_presigned_urls(
        self,
        presigned_url_body: PresignedUrlBody,
    ) -> PresignedUrlResp:
        try:
            if presigned_url_body.parts == 1:
                url = create_presigned_url(bucket_name=_SETTINGS.MINIO_LANDINGZONE_BUCKET,
                                           object_name=presigned_url_body.object_name)
                b64url = base64.b64encode(url.encode("utf-8")).decode()
                return PresignedUrlResp(upload_id="", urls=[b64url])
            else:

                uploadId, urls = create_presigned_urls_multipart(bucket_name=_SETTINGS.MINIO_LANDINGZONE_BUCKET,
                                                                 object_name=presigned_url_body.object_name,
                                                                 part_count=presigned_url_body.parts)
                b64urls: List[str] = [base64.b64encode(b[1].encode("utf-8")).decode() for b in urls]
                return PresignedUrlResp(upload_id=uploadId, urls=b64urls)
        except Exception as e:
            print(e)
            return JSONResponse(content={"error": str(e)}, status_code=500)
