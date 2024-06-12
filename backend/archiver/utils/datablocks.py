import subprocess
import tarfile
import os
import shutil
from uuid import uuid4
from typing import Iterator, List
from pathlib import Path

from archiver.utils.working_storage_interface import S3Storage, Bucket
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.utils.log import getLogger
from archiver.config.variables import Variables
from archiver.flows.utils import DatasetError, SystemError, StoragePaths


def create_tarballs(dataset_id: int, folder: Path,
                    target_size: int = 300 * (1024**2)) -> List[Path]:
    """_summary_

    Args:
        dataset_id (int): _description_
        folder (Path): _description_
        target_size (int, optional): _description_. Defaults to 300*(1024**2).

    Returns:
        List[Path]: _description_
    """

    # TODO: corner case: target size < file size
    tarballs: List[Path] = []

    filename: Path = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
    filepath = folder / filename

    tar = tarfile.open(filepath, 'x:gz', compresslevel=4)

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


def calculate_checksum(filename: Path, chunksize: int = 1024 * 1025) -> str:
    """Calculate an md5 hash of a file

    Args:
        filename (Path): absolute or relative path to file
        chunksize (int, optional): default chunk size to calculate hash on. Defaults to 1024*1025.

    Returns:
        str: hash as str
    """
    import hashlib
    m = hashlib.md5()
    with open(filename, 'rb') as f:
        while chunk := f.read(chunksize):
            m.update(chunk)
    return m.hexdigest()


def download_object_from_s3(bucket: Bucket, folder: Path, object_name: str, target_path: Path):
    """Download an object from S3 storage.

    Args:
        bucket (Bucket): Bucket to look for file
        folder (Path): s3 prefix for object
        object_name (str): object name, no prefix
        target_path (Path): absolute or relative path for the file to be created
    """
    S3Storage().fget_object(bucket=bucket, folder=str(folder), object_name=object_name, target_path=target_path)


def list_s3_objects(prefix: Path, bucket: Bucket) -> Iterator[object]:
    """List all objects in s3 bucket and path

    Args:
        minio_prefix (Path): prefix for files to be listed
        bucket (Bucket): s3 bucket

    Returns:
        _type_: Iterator to objects
    """
    getLogger().debug(f"Minio: {S3Storage().url}")
    return S3Storage().list_objects(bucket, str(prefix))


def download_objects_from_s3(prefix: Path, bucket: Bucket, destination_folder: Path) -> List[Path]:
    """Download objects form s3 storage to folder

    Args:
        prefix (Path): S3 prefix
        bucket (Bucket): s3 bucket
        destination_folder (Path): Target folder. Will be created if it does not exist.

    Returns:
        List[Path]: List of paths of created files
    """
    destination_folder.mkdir(parents=True, exist_ok=True)

    files: List[Path] = []

    for item in S3Storage().list_objects(bucket, str(prefix)):
        local_filepath = destination_folder / Path(item.object_name or "")
        local_filepath.parent.mkdir(parents=True, exist_ok=True)
        S3Storage().fget_object(bucket=bucket, folder=str(prefix), object_name=item.object_name or "", target_path=local_filepath)
        files.append(local_filepath)

    return files


def upload_objects_to_s3(prefix: Path, bucket: Bucket, source_folder: Path, ext: str | None = None) -> List[Path]:
    uploaded_files: List[Path] = []
    for filepath in (f for f in source_folder.iterdir() if not ext or f.suffix == ext):
        minio_path: Path = prefix / filepath.name
        S3Storage().fput_object(source_folder / filepath.name, minio_path, bucket)
        uploaded_files.append(filepath)
    return uploaded_files


def delete_objects_from_s3(prefix: Path, bucket: Bucket):
    getLogger().info(f"Cleaning up objects in {bucket.name}/{prefix}")
    S3Storage().delete_object(minio_prefix=prefix, bucket=bucket)


def create_datablock_entries(
        dataset_id: int, folder: Path, origDataBlocks: List[OrigDataBlock],
        tarballs: List[Path]) -> List[DataBlock]:
    """Create datablock entries compliant with schema provided by scicat

    Args:
        dataset_id (int): Dataset identifier
        folder (Path): _description_
        origDataBlocks (List[OrigDataBlock]): _description_
        tarballs (List[Path]): _description_

    Returns:
        List[DataBlock]: _description_
    """
    datablocks: List[DataBlock] = []
    for tar in tarballs:
        o = origDataBlocks[0]

        data_file_list: List[DataFile] = []

        tar_path = folder / tar

        md5_hash = calculate_checksum(tar_path)

        tarball = tarfile.open(tar_path)

        for tar_info in tarball.getmembers():
            data_file_list.append(DataFile(
                path=tar_info.path,
                size=tar_info.size,
                # time=tar_info.mtime
                chk=str(md5_hash),
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
            archiveId=str(StoragePaths.relative_datablocks_folder(dataset_id) / tar_path.name),
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


def find_object_in_s3(dataset_id, datablock_name):
    object_found = next((x
                         for x in list_s3_objects(
                             prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                             bucket=S3Storage().STAGING_BUCKET) if x.object_name == datablock_name),
                        False)

    return object_found


def move_data_to_LTS(dataset_id: int, datablock: DataBlock) -> str:

    # mount target dir and check access
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(
            f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    datablock_name = datablock.archiveId

    getLogger().info(f"Searching datablock {datablock_name}")

    object_found = find_object_in_s3(dataset_id, datablock_name)

    if not object_found:
        raise DatasetError(f"Datablock {datablock_name} not found in storage at {StoragePaths.relative_datablocks_folder(dataset_id)}")

    getLogger().info(f"Downloading datablock {datablock_name}")

    datablocks_scratch_folder = StoragePaths.scratch_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name

    download_object_from_s3(bucket=S3Storage().STAGING_BUCKET, folder=StoragePaths.relative_datablocks_folder(
        dataset_id), object_name=str(StoragePaths.relative_datablocks_folder(dataset_id) / datablock_name), target_path=datablock_full_path)

    getLogger().info("Calculating Checksum.")
    checksum_hash_source = calculate_checksum(datablock_full_path)

    # TODO: Compare checksum against entry in datablock

    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    lts_target_dir.mkdir(parents=True, exist_ok=True)

    getLogger().info("Copy datablock to LTS")

    # Copy to LTS
    copy_file(src=datablock_full_path.absolute(), dst=lts_target_dir.absolute())

    destination = lts_target_dir / datablock_name

    getLogger().info("Verifying checksum")
    checksum_destination = calculate_checksum(destination)

    if checksum_destination != checksum_hash_source:
        raise SystemError("Datablock verification failed")

    return checksum_hash_source


def copy_file(src: Path, dst: Path):
    subprocess.run(["rsync", "-rcvz", "--stats", "--mkpath", str(src), str(dst)], capture_output=True, check=True)


def verify_data_in_LTS(dataset_id: int, datablock: DataBlock, expected_checksum: str) -> None:

    dst_folder = StoragePaths.scratch_datablocks_folder(dataset_id) / "verification"
    dst_folder.mkdir(parents=True, exist_ok=True)
    local_datablock_path = dst_folder / Path(datablock.archiveId).name

    lts_datablock_path = StoragePaths.lts_datablocks_folder(dataset_id) / Path(datablock.archiveId).name

    copy_file(src=lts_datablock_path.absolute(), dst=dst_folder.absolute())

    checksum = calculate_checksum(local_datablock_path)

    if checksum != expected_checksum:
        raise SystemError(f"Datablock verification failed: expected checksum {expected_checksum} but got actual {checksum}")

    os.remove(local_datablock_path)


def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    getLogger().info(f"Creating datablocks for {dataset_id}")

    if len(origDataBlocks) == 0:
        return []

    if all(False for _ in list_s3_objects(StoragePaths.relative_datablocks_folder(dataset_id), S3Storage().LANDINGZONE_BUCKET)):
        raise Exception(
            f"No objects found in landing zone at {StoragePaths.relative_datablocks_folder(dataset_id)} for dataset {dataset_id}. Storage endpoint: {S3Storage().url}")

    dataset_scratch_folder = StoragePaths.scratch_folder(dataset_id)

    # import shutil
    # shutil.rmtree(dataset_scratch_folder)

    dataset_scratch_folder.mkdir(parents=True, exist_ok=True)

    # files with full path are downloaded to scratch root
    file_paths = download_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=S3Storage().LANDINGZONE_BUCKET, destination_folder=StoragePaths.scratch_root())

    getLogger().info(
        f"Downloaded {len(file_paths)} objects from {S3Storage().LANDINGZONE_BUCKET}")

    datablocks_scratch_folder = StoragePaths.scratch_datablocks_folder(dataset_id)

    tarballs = create_tarballs(dataset_id=dataset_id, folder=datablocks_scratch_folder)

    getLogger().info(
        f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(
        dataset_id, StoragePaths.scratch_datablocks_folder(dataset_id), origDataBlocks, tarballs)

    uploaded_objects = upload_objects_to_s3(prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=S3Storage().STAGING_BUCKET, source_folder=datablocks_scratch_folder, ext=".gz")

    missing_objects = verify_objects(uploaded_objects, minio_prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=S3Storage().STAGING_BUCKET, source_folder=datablocks_scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    return datablocks


def cleanup_lts_folder(dataset_id: int) -> None:
    # TODO: is deletion possible?
    lts_folder = StoragePaths.lts_datablocks_folder(dataset_id)

    import random
    import string
    suffix = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))

    lts_folder_new = lts_folder.rename(str(lts_folder) + "_failed_" + suffix)
    getLogger().info(f"Move LTS folder from {lts_folder} to {lts_folder_new}")
    shutil.move(src=lts_folder, dst=lts_folder_new)


def cleanup_staging(dataset_id: int) -> None:
    delete_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                           bucket=S3Storage().STAGING_BUCKET)


def cleanup_landingzone(dataset_id: int) -> None:
    delete_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                           bucket=S3Storage().LANDINGZONE_BUCKET)


def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not S3Storage().stat_object(
                filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


def cleanup_scratch(dataset_id: int):
    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_datablocks_folder(dataset_id)}")
    shutil.rmtree(StoragePaths.scratch_datablocks_folder(dataset_id))

    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")
