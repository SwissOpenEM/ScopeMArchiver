import base64
from typing import List

from fastapi.responses import JSONResponse
from openapi_server.impl.scicat import mark_dataset_as_archivable, start_archiving
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.abort_upload_resp import AbortUploadResp
from openapi_server.models.finalize_dataset_upload_body import FinalizeDatasetUploadBody
from openapi_server.models.finalize_dataset_upload_resp import FinalizeDatasetUploadResp
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp

from openapi_server.apis.s3upload_api_base import BaseS3uploadApi
from openapi_server.settings import GetSettings

from .s3 import (
    complete_multipart_upload,
    abort_multipart_upload,
    create_presigned_url,
    create_presigned_urls_multipart,
)

from logging import getLogger

_LOGGER = getLogger("uvicorn.presignedurls")


class BaseS3UploadApiImpl(BaseS3uploadApi):
    async def complete_upload(  # type: ignore
        self,
        complete_upload_body: CompleteUploadBody,
    ) -> CompleteUploadResp:
        try:
            return complete_multipart_upload(GetSettings().MINIO_LANDINGZONE_BUCKET, complete_upload_body)
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(
                status_code=500, content={"message": "Failed to complete upload", "details": str(e)}
            )

    async def abort_multipart_upload(
        self,
        abort_upload_body: AbortUploadBody,
    ) -> AbortUploadResp:
        try:
            abort_multipart_upload(
                bucket_name=GetSettings().MINIO_LANDINGZONE_BUCKET,
                object_name=abort_upload_body.object_name,
                upload_id=abort_upload_body.upload_id,
            )
            return AbortUploadResp(
                message="Abortin multipart upload succeeded.",
                upload_id=abort_upload_body.upload_id,
                object_name=abort_upload_body.object_name,
            )
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(
                status_code=500, content={"message": "Failed to abort multipart upload", "details": str(e)}
            )

    async def get_presigned_urls(
        self,
        presigned_url_body: PresignedUrlBody,
    ) -> PresignedUrlResp:
        try:
            if presigned_url_body.parts == 1:
                url = create_presigned_url(
                    bucket_name=GetSettings().MINIO_LANDINGZONE_BUCKET,
                    object_name=presigned_url_body.object_name,
                )
                b64url = base64.b64encode(url.encode("utf-8")).decode()
                _LOGGER.debug("Presigned Url created: %s", url)
                return PresignedUrlResp(upload_id="", urls=[b64url])
            else:
                uploadId, urls = create_presigned_urls_multipart(
                    bucket_name=GetSettings().MINIO_LANDINGZONE_BUCKET,
                    object_name=presigned_url_body.object_name,
                    part_count=presigned_url_body.parts,
                )
                b64urls: List[str] = [base64.b64encode(b[1].encode("utf-8")).decode() for b in urls]
                _LOGGER.debug("Presigned Urls created: %s", urls)
                return PresignedUrlResp(upload_id=uploadId, urls=b64urls)
        except Exception as e:
            _LOGGER.error(str(e))
            return JSONResponse(
                status_code=500, content={"message": "Failed to get presigned urls", "details": str(e)}
            )

    async def finalize_dataset_upload(
        self, finalize_dataset_upload_body: FinalizeDatasetUploadBody
    ) -> FinalizeDatasetUploadResp:
        try:
            await mark_dataset_as_archivable(finalize_dataset_upload_body.dataset_pid)
            if finalize_dataset_upload_body.create_archiving_job:
                await start_archiving(
                    dataset_pid=finalize_dataset_upload_body.dataset_pid,
                    owner_user=finalize_dataset_upload_body.owner_user,
                    contact_email=finalize_dataset_upload_body.contact_email,
                    owner_group=finalize_dataset_upload_body.owner_group,
                )
            return FinalizeDatasetUploadResp(
                dataset_id=finalize_dataset_upload_body.dataset_pid, message="Dataset upload finalized"
            )
        except Exception as e:
            _LOGGER.error(e)
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Failed to finalize dataset",
                    "dataset_id": finalize_dataset_upload_body.dataset_pid,
                    "details": str(e),
                },
            )
