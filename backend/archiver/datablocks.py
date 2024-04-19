import tarfile
import os
import requests
from uuid import uuid4
from typing import List, Set

from pathlib import Path

from .working_storage_interface import minioClient, Bucket
from .model import OrigDataBlock, DataBlock, DataFile
from .logging import getLogger

_SCRATCH_FOLDER = Path(os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch"))
_LTS_ROOT = Path(os.environ.get('LTS_STORAGE_ROOT', "/tmp/LTS"))


def create_tarballs(dataset_id: int, folder: Path,
                    target_size: int = 300 * (1024**2)) -> List[Path]:

    # TODO: corner case: target size < file size
    tarballs: List[Path] = []

    filename: Path = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
    filepath = folder / filename

    tar = tarfile.open(filepath, 'x:gz', compresslevel=6)

    for f in folder.iterdir():
        file = folder / f
        if file.suffix == ".gz":
            continue
        tar.add(file, recursive=False)

        if filepath.stat().st_size >= target_size:
            tar.close()
            tarballs.append(filename)
            filename = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
            filepath = folder / filename
            tar = tarfile.open(filepath, 'w')

    tar.close()
    tarballs.append(filename)

    return tarballs


def find_objects(minio_prefix: str, bucket: Bucket):
    getLogger().debug(f"Minio: {minioClient.url}")
    return minioClient.get_objects(bucket, minio_prefix)


def download_objects(minio_prefix: str, bucket: Bucket, destination_folder: Path) -> List[Path]:

    if not destination_folder.exists():
        raise FileNotFoundError(f"Destination folder {destination_folder} not reachable")

    files: List[Path] = []

    for object in minioClient.get_objects(bucket, minio_prefix):
        object_name = object.object_name if object.object_name is not None else ""
        presigned_url = minioClient.get_presigned_url(
            filename=object_name, bucket=bucket)
        minioClient.stat_object(
            filename=object_name, bucket=bucket)
        local_filepath = destination_folder / object_name

        with requests.get(presigned_url, stream=True) as r:
            r.raise_for_status()
            chunk_size = 8192
            with open(local_filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
        files.append(local_filepath)
    return files


def upload_objects(minio_prefix: Path, bucket: Bucket, source_folder: Path, ext: str | None = None) -> List[Path]:
    uploaded_files: List[Path] = []
    for filepath in (f for f in source_folder.iterdir() if not ext or f.suffix == ext):
        minio_path: Path = minio_prefix / filepath.name
        minioClient.put_object(source_folder / filepath, minio_path, bucket)
        uploaded_files.append(filepath)
    return uploaded_files


def delete_objects(minio_prefix: Path, bucket: Bucket):
    getLogger().info(f"Cleaning up objects in {bucket.name}/{minio_prefix}")
    minioClient.delete_object(minio_prefix=minio_prefix, bucket=bucket)


def create_datablock_entries(
        dataset_id: int, folder: Path, origDataBlocks: List[OrigDataBlock],
        tarballs: List[Path]) -> List[DataBlock]:

    datablocks: List[DataBlock] = []
    for tar in tarballs:
        o = origDataBlocks[0]

        data_file_list: List[DataFile] = []

        tar_path = folder / tar
        tarball = tarfile.open(tar_path)

        for tar_info in tarball.getmembers():
            data_file_list.append(DataFile(
                path=tar_info.path,
                size=tar_info.size,
                # time=tar_info.mtime
                chk=str(tar_info.chksum),
                uid=str(tar_info.uid),
                gid=str(tar_info.gid),
                perm=str(tar_info.mode),
                createdBy=str(tar_info.uname),
                updatedBy=str(tar_info.uname),
                # createdAt=tar_info.mtime,
                # updatedAt=tar_info.mtime
            ))

        datablocks.append(DataBlock(
            id=str(uuid4()),
            archiveId=str(uuid4()),
            size=1,
            packedSize=1,
            chkAlg="md5",
            version=str(1),
            ownerGroup=o.ownerGroup,
            accessGroups=o.accessGroups,
            instrumentGroup=o.instrumentGroup,
            # createdBy=
            # updatedBy=
            # updatedAt=datetime.datetime.isoformat(),
            datasetId=str(dataset_id),
            dataFileList=data_file_list,
            rawDatasetId=o.rawdatasetId,
            derivedDatasetId=o.derivedDatasetId
        ))

    return datablocks


def move_data_to_LTS(dataset_id: int, datablocks: List[DataBlock]) -> None:

    # mount target dir and check access
    if not _LTS_ROOT.exists():
        raise FileNotFoundError(f"Can't open LTS root {_LTS_ROOT}")

    lts_target_dir: Path = _LTS_ROOT / str(dataset_id)
    lts_target_dir.mkdir(parents=False, exist_ok=True)

    # TODO: set permissions

    archive_ids: Set[str] = set(map(lambda d: d.archiveId, datablocks))

    # find objects
    for obj in find_objects(str(dataset_id), minioClient.STAGING_BUCKET):
        archive_ids.discard(obj.object_name)

    # TODO: set correct id/path in LTS

    # if not len(archive_ids) == 0:
    #     missing_blocks = ", ".join(archive_ids)
    #     raise Exception(f"Not all datablocks found: {missing_blocks}")

    # download to target dir
    archived_objects = download_objects(minio_prefix=str(dataset_id), bucket=minioClient.STAGING_BUCKET, destination_folder=_LTS_ROOT)

    assert len(archived_objects) == len(datablocks)

    # TODO:
    # for a in datablocks:
    #     if Path(a.archiveId).stat().st_size != a.packedSize:
    #         raise Exception(f"Size mismatch: {a.archiveId}")

    # quick verify


def validate_data_in_LTS(datablocks: List[DataBlock]) -> None:
    pass


def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    getLogger().info(f"Creating datablocks for {dataset_id}")

    if len(origDataBlocks) == 0:
        return []

    if all(False for _ in find_objects(str(dataset_id), minioClient.LANDINGZONE_BUCKET)):
        raise Exception(f"No objects found for dataset {dataset_id}")

    scratch_folder = _SCRATCH_FOLDER / "archival" / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    file_paths = download_objects(minio_prefix=str(dataset_id), bucket=minioClient.LANDINGZONE_BUCKET,
                                  destination_folder=_SCRATCH_FOLDER / "archival")

    getLogger().info(f"Downloaded {len(file_paths)} objects from {minioClient.LANDINGZONE_BUCKET}")

    tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    getLogger().info(f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(dataset_id, scratch_folder, origDataBlocks, tarballs)

    uploaded_objects = upload_objects(minio_prefix=Path(str(dataset_id)), bucket=minioClient.STAGING_BUCKET,
                                      source_folder=scratch_folder, ext=".gz")

    missing_objects = verify_objects(uploaded_objects, minio_prefix=Path(str(dataset_id)), bucket=minioClient.STAGING_BUCKET,
                                     source_folder=scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    # regular cleanup
    delete_objects(minio_prefix=Path(str(dataset_id)), bucket=minioClient.LANDINGZONE_BUCKET)
    cleanup_scratch(dataset_id, "archival")

    return datablocks


def cleanup_staging(dataset_id: int) -> None:
    delete_objects(minio_prefix=Path(str(dataset_id)), bucket=minioClient.STAGING_BUCKET)


def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not minioClient.stat_object(
                filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


def cleanup_scratch(dataset_id: int, folder_type: str):
    if folder_type not in ["archival", "retrieval"]:
        raise Exception(f"No valid folder_type to delete: {folder_type}")
    scratch_folder = _SCRATCH_FOLDER / folder_type / str(dataset_id)
    getLogger().debug(f"Cleaning up objects in scratch folder: {scratch_folder}")
    # import shutil
    # shutil.rmtree(scratch_folder)


def create_dummy_dataset(dataset_id: int):
    scratch_folder = _SCRATCH_FOLDER / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    for i in range(10):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs=64M count=2 iflag=fullblock")

    upload_objects(minio_prefix=Path(str(dataset_id)), bucket=minioClient.LANDINGZONE_BUCKET,
                   source_folder=scratch_folder)


__all__ = [
    "create_datablocks",
    "move_data_to_LTS",
    "validate_data_in_LTS",
    "create_dummy_dataset",
    "cleanup_scratch",
    "cleanup_staging"
]
