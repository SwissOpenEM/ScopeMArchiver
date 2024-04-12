import datetime
from typing import List
from .model import OrigDataBlock, DataBlock, DataFile
import os
import tarfile
from .working_storage_interface import minioClient, Bucket

_SCRATCH_FOLDER = os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch")


def create_tarballs(dataset_id: int, folder: os.PathLike,
                    target_size: int = 100 * (1024**3)) -> List[os.PathLike]:

    tarballs = []

    filename = f"{dataset_id}_{len(tarballs)}.tar.gz"
    filepath = os.path.join(folder, filename)

    tar = tarfile.open(filepath, 'x:gz')

    for f in os.listdir(folder):
        file = os.path.join(folder, f)
        if file.endswith(".tar.gz"):
            continue
        tar.add(file, recursive=False)

        if os.path.getsize(filepath) >= target_size:
            tar.close()
            tarballs.append(filename)
            filename = f"{dataset_id}_{len(tarballs)}.tar.gz"
            filepath = os.path.join(folder, filename)
            tar = tarfile.open(filepath, 'w')

    tar.close()
    tarballs.append(filename)

    return tarballs


def download_objects(minio_prefix: str, bucket: Bucket, destination_folder: os.PathLike):

    if not os.path.exists(destination_folder):
        print("Destination not reachable")
        return

    for filename in minioClient.get_objects(minio_prefix, bucket):
        presigned_url = minioClient.get_presigned_url(
            filename=filename, bucket=bucket)
        stat = minioClient.stat_object(
            filename=filename, bucket=bucket)
        local_filename = os.path.join(
            destination_folder, filename)

        with requests.get(presigned_url, stream=True) as r:
            r.raise_for_status()
            chunk_size = 8192
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)


def upload_objects(minio_prefix: str, bucket: Bucket, source_folder: os.PathLike):
    for filename in os.listdir(source_folder):
        minioClient.put_object(filename, os.path.join(
            minio_prefix, filename), bucket)


def delete_objects(minio_prefix: str, bucket: Bucket):
    pass


def create_datablock_entries(dataset_id, origDataBlocks, tarballs) -> List[DataBlock]:
    datablocks = []
    for tar in tarballs:
        o = origDataBlocks[0]

        data_file_list = []

        tarball = tarfile.open(tar)
        for tar_info in tarball.getmembers():
            data_file_list.append(DataFile(
                path=tar_info.path,
                size=tar_info.size,
                # time=tar_info.mtime
                chk=tar_info.chksum,
                uid=tar_info.uid,
                guid=tar_info.gid,
                perm=tar_info.mode,
                createdBy=tar_info.uname,
                updatedBy=tar_info.uname
                # createdAt=tar_info.mtime,
                # updatedAt=tar_info.mtime
            ))

        datablocks.append(DataBlock(
            id=str(uuid4()),
            archiveId=str(uuid4()),
            packedSize=1,
            chkAlg="md5",
            version=1,
            ownerGroup=o.ownerGroup,
            accessGroups=o.accessGroups,
            instrumentGroup=o.instrumentGroup,
            # createdBy=
            # updatedBy=
            updatedAt=datetime.datetime.isoformat(),
            datasetId=dataset_id,
            dataFileList=data_file_list,
            rawDatasetId=o.rawdatasetId,
            derivedDatasetId=o.derivedDatasetId
        ))

    return datablocks


def move_data_to_staging(datablocks: List[DataBlock]) -> List[DataBlock]:
    pass


def move_data_to_LTS(datablocks: List[DataBlock]) -> None:
    pass


def validate_data_in_LTS(datablocks: List[DataBlock]) -> None:
    pass


def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    datablocks = []
    for o in origDataBlocks:
        d = DataBlock(
            id=str(o.id),
            archiveId=f"/path/to/archived/{o.id}.tar.gz",
            size=o.size,
            packedSize=o.size,
            version=str(1),
            ownerGroup="me"
        )
        datablocks.append(d)
    return datablocks

    # if len(origDataBlocks) == 0:
    #     return

    # scratch_folder = os.path.join(_SCRATCH_FOLDER, str(dataset_id))
    # if not os.path.exists(scratch_folder):
    #     os.makedirs(scratch_folder)

    # download_objects(minio_prefix=dataset_id, bucket=minioClient.LANDINGZONE_BUCKET,
    #                  destination_folder=scratch_folder)

    # tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    # datablocks = create_datablock_entries(dataset_id, origDataBlocks, tarballs)

    # upload_objects(minio_prefix=dataset_id, bucket=minioClient.ARCHIVAL_BUCKET,
    #                source_folder=scratch_folder)

    # delete_objects(minio_prefix=dataset_id, bucket=minioClient.LANDINGZONE_BUCKET)

    # return datablocks


__all__ = [
    "create_datablocks",
    "move_data_to_staging",
    "move_data_to_LTS",
    "validate_data_in_LTS"
]
