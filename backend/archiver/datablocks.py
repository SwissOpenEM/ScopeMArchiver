import tarfile
import os
import requests
from uuid import uuid4
from typing import List, Set

from pathlib import Path

from .working_storage_interface import MinioStorage, Bucket
from .model import OrigDataBlock, DataBlock, DataFile
from .log import getLogger
from .config.variables import Variables
from .flows.utils import DatasetError, SystemError


def create_tarballs(dataset_id: int, folder: Path,
                    target_size: int = 300 * (1024**2)) -> List[Path]:

    # TODO: corner case: target size < file size
    tarballs: List[Path] = []

    filename: Path = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
    filepath = folder / filename

    tar = tarfile.open(filepath, 'x:gz', compresslevel=6)

    for f in folder.iterdir():
        file = f
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
    getLogger().debug(f"Minio: {MinioStorage().url}")
    return MinioStorage().get_objects(bucket, minio_prefix)


def download_objects(minio_prefix: str, bucket: Bucket, destination_folder: Path) -> List[Path]:

    if not destination_folder.exists():
        raise FileNotFoundError(f"Destination folder {destination_folder} not reachable")

    files: List[Path] = []

    for object in MinioStorage().get_objects(bucket, minio_prefix):
        object_name = object.object_name if object.object_name is not None else ""
        presigned_url = MinioStorage().get_presigned_url(
            filename=object_name, bucket=bucket)
        MinioStorage().stat_object(
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
        MinioStorage().put_object(source_folder / filepath.name, minio_path, bucket)
        uploaded_files.append(filepath)
    return uploaded_files


def delete_objects(minio_prefix: Path, bucket: Bucket):
    getLogger().info(f"Cleaning up objects in {bucket.name}/{minio_prefix}")
    MinioStorage().delete_object(minio_prefix=minio_prefix, bucket=bucket)


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


def create_lts_path(dataset_id: int) -> Path:
    return Variables().LTS_STORAGE_ROOT / str(dataset_id)


def move_data_to_LTS(dataset_id: int, datablocks: List[DataBlock]) -> None:

    # mount target dir and check access
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    lts_target_dir = create_lts_path(dataset_id)
    lts_target_dir.mkdir(parents=False, exist_ok=True)

    # TODO: set permissions

    archive_ids: Set[str] = set(map(lambda d: d.archiveId, datablocks))

    # find objects
    for obj in find_objects(str(dataset_id), MinioStorage().STAGING_BUCKET):
        archive_ids.discard(obj.object_name)

    # TODO: set correct id/path in LTS

    # if not len(archive_ids) == 0:
    #     missing_blocks = ", ".join(archive_ids)
    #     raise Exception(f"Not all datablocks found: {missing_blocks}")

    # download to target dir
    archived_objects = download_objects(minio_prefix=str(dataset_id), bucket=MinioStorage().STAGING_BUCKET,
                                        destination_folder=Variables().LTS_STORAGE_ROOT)

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

    if all(False for _ in find_objects(str(dataset_id), MinioStorage().LANDINGZONE_BUCKET)):
        raise Exception(f"No objects found for dataset {dataset_id}")

    scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / "archival" / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    file_paths = download_objects(minio_prefix=str(dataset_id), bucket=MinioStorage().LANDINGZONE_BUCKET,
                                  destination_folder=Variables().ARCHIVER_SCRATCH_FOLDER / "archival")

    getLogger().info(f"Downloaded {len(file_paths)} objects from {MinioStorage().LANDINGZONE_BUCKET}")

    tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    getLogger().info(f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(dataset_id, scratch_folder, origDataBlocks, tarballs)

    uploaded_objects = upload_objects(minio_prefix=Path(str(dataset_id)), bucket=MinioStorage().STAGING_BUCKET,
                                      source_folder=scratch_folder, ext=".gz")

    missing_objects = verify_objects(uploaded_objects, minio_prefix=Path(str(dataset_id)), bucket=MinioStorage().STAGING_BUCKET,
                                     source_folder=scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    # regular cleanup
    delete_objects(minio_prefix=Path(str(dataset_id)), bucket=MinioStorage().LANDINGZONE_BUCKET)
    cleanup_scratch(dataset_id, "archival")

    return datablocks


def cleanup_lts_folder(dataset_id: int) -> None:
    lts_folder = create_lts_path(dataset_id)

    # import shutil
    # shutil.rmtree(lts_folder, ignore_errors=True)


def cleanup_staging(dataset_id: int) -> None:
    delete_objects(minio_prefix=Path(str(dataset_id)), bucket=MinioStorage().STAGING_BUCKET)


def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not MinioStorage().stat_object(
                filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


def cleanup_scratch(dataset_id: int, folder_type: str):
    if folder_type not in ["archival", "retrieval"]:
        raise Exception(f"No valid folder_type to delete: {folder_type}")
    scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / folder_type / str(dataset_id)
    getLogger().debug(f"Cleaning up objects in scratch folder: {scratch_folder}")

    # import shutil
    # shutil.rmtree(scratch_folder)
    # for d in datablocks:
    #     for f in d.dataFileList or []:
    #         os.remove(f.path)


__all__ = [
    "create_datablocks",
    "move_data_to_LTS",
    "validate_data_in_LTS",
    "cleanup_scratch",
    "cleanup_staging",
]
