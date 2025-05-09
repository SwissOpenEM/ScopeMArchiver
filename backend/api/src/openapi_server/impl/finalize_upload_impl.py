from fastapi.responses import JSONResponse
from openapi_server.apis.s3upload_api_base import BaseS3uploadApi
from openapi_server.models.finalize_dataset_upload_body import FinalizeDatasetUploadBody
from openapi_server.impl.scicat import mark_dataset_as_archivable, start_archiving

from logging import getLogger

from openapi_server.models.finalize_dataset_upload_resp import FinalizeDatasetUploadResp

_LOGGER = getLogger("uvicorn.finalize_upload")


class FinalizeDatasetUploadImpl(BaseS3uploadApi):
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
                DatasetID=finalize_dataset_upload_body.dataset_pid, Message="Dataset upload finalized"
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
