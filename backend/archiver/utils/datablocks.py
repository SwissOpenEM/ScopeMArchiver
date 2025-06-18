from dataclasses import dataclass
import subprocess
import tarfile
import os
import shutil
import asyncio
import time
import datetime
import hashlib

from typing import Callable, Dict, Generator, List
from pathlib import Path

from archiver.utils.s3_storage_interface import S3Storage, Bucket
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.utils.log import getLogger, log, log_debug
from archiver.config.variables import Variables
from archiver.flows.utils import DatasetError, SystemError, StoragePaths


@log
def get_all_files_relative(folder) -> List[Path]:
    relative_files = []
    for i, j, k in os.walk(folder):
        for f in k:
            relative_files.append(Path(i).joinpath(f).relative_to(folder))
    return relative_files


@log
def unpack_tarballs(src_folder: Path, dst_folder: Path):
    if not any(Path(src_folder).iterdir()):
        raise SystemError(f"Empty folder {src_folder} found. No files to unpack.")

    for file in src_folder.iterdir():
        if not tarfile.is_tarfile(file):
            continue

        getLogger().info(f"Start extracting {file} to {dst_folder}")

        tar = tarfile.open(file)
        tar.extractall(path=dst_folder)

        getLogger().info(f"Done extracting {file} to {dst_folder}")


@dataclass
class ArchiveInfo:
    unpackedSize: int
    packedSize: int
    path: Path


def partition_files_flat(folder: Path, target_size_bytes: int) -> Generator[List[Path], None, None]:
    """Partitions files in folder into groups such that all the files in a group combined
    have a target_size_bytes size at maximum. Folders are not treated recursively

    Args:
        folder (Path): Folder to partition files in
        target_size_bytes (int): maximum size of grouped files

    Yields:
        Generator[List[Path], None, None]: List of paths with maximum size
    """

    if not folder.is_dir():
        yield None

    part: List[Path] = []
    size = 0
    idx = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            filepath = Path(os.path.join(dirpath, filename))
            if size + os.path.getsize(filepath) > target_size_bytes:
                yield part
                part = []
                size = 0
                idx = idx + 1
            part.append(filepath.relative_to(folder))
            size = size + os.path.getsize(filepath)

    yield part


@log_debug
def create_tarfiles(
    dataset_id: str,
    src_folder: Path,
    dst_folder: Path,
    target_size: int,
    progress_callback: Callable[[float], None] = None
) -> List[ArchiveInfo]:
    """Create datablocks, i.e. .tar.gz files, from all files in a folder. Folder structures are kept and symlnks not resolved.
    The created tar files will be named according to the dataset they belong to.

    Args:
        dataset_id (str): dataset identifier
        src_folder (Path): source folder to find files to create tars from
        dst_folder (Path): destination folder to write the tar files to
        target_size (int, optional): Target size of the tar file. This is the unpacked size of the files.

    Returns:
        List[Path]: _description_
    """

    # TODO: corner case: target size < file size
    tarballs: List[ArchiveInfo] = []
    tar_name = dataset_id.replace("/", "-")

    if not any(Path(src_folder).iterdir()):
        raise SystemError(f"Empty folder {src_folder} found.")

    total_file_count = sum(len(files) for _, _, files in os.walk(src_folder))
    current_file_count = 0

    for files in partition_files_flat(src_folder, target_size):
        current_tar_info = ArchiveInfo(
            unpackedSize=0,
            packedSize=0,
            path=Path(dst_folder / Path(f"{tar_name}_{len(tarballs)}.tar.gz")),
        )
        current_tarfile: tarfile.TarFile = tarfile.open(current_tar_info.path, "w")
        for relative_file_path in files:
            full_path = src_folder.joinpath(relative_file_path)
            current_tar_info.unpackedSize += full_path.stat().st_size
            current_tarfile.add(name=full_path, arcname=relative_file_path)
            current_file_count += 1
            if progress_callback is not None:
                progress_callback(1.0 * current_file_count / total_file_count)

        current_tarfile.close()
        current_tar_info.packedSize = current_tar_info.path.stat().st_size
        tarballs.append(current_tar_info)

    return tarballs


def calculate_md5_checksum(filename: Path, chunksize: int = 2**20) -> str:
    """Calculate an md5 hash of a file

    Args:
        filename (Path): absolute or relative path to file
        chunksize (int, optional): default chunk size to calculate hash on. Defaults to 1024*1025.

    Returns:
        str: hash as str
    """
    import hashlib

    m = hashlib.md5()
    with open(filename, "rb") as f:
        while chunk := f.read(chunksize):
            m.update(chunk)
    return m.hexdigest()


def calculate_checksum(dataset_id: str, datablock: DataBlock) -> str:
    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name
    return calculate_md5_checksum(datablock_full_path)


@log_debug
def download_object_from_s3(
    client: S3Storage, bucket: Bucket, folder: Path, object_name: str, target_path: Path
):
    """Download an object from S3 storage.

    Args:
        bucket (Bucket): Bucket to look for file
        folder (Path): s3 prefix for object
        object_name (str): object name, no prefix
        target_path (Path): absolute or relative path for the file to be created
    """
    client.fget_object(
        bucket=bucket,
        folder=str(folder),
        object_name=object_name,
        target_path=target_path,
    )


@log
def list_datablocks(client: S3Storage, prefix: Path, bucket: Bucket) -> List[S3Storage.ListedObject]:
    """List all objects in s3 bucket and path

    Args:
        minio_prefix (Path): prefix for files to be listed
        bucket (Bucket): s3 bucket

    Returns:
        _type_: Iterator to objects
    """
    return client.list_objects(bucket, str(prefix))


@log
def download_objects_from_s3(
    client: S3Storage, prefix: Path, bucket: Bucket, destination_folder: Path, progress_callback
) -> List[Path]:
    """Download objects form s3 storage to folder

    Args:
        prefix (Path): S3 prefix
        bucket (Bucket): s3 bucket
        destination_folder (Path): Target folder. Will be created if it does not exist.

    Returns:
        List[Path]: List of paths of created files
    """
    destination_folder.mkdir(parents=True, exist_ok=True)

    files = client.download_objects(minio_prefix=prefix, bucket=bucket,
                                    destination_folder=destination_folder, progress_callback=progress_callback)

    if len(files) == 0:
        raise SystemError(f"No files found in bucket {bucket.name} at {prefix}")

    return files


@log
def find_missing_datablocks_in_s3(client: S3Storage, datablocks: List[DataBlock], bucket: Bucket) -> List[DataBlock]:

    datablocks_not_in_retrieval_bucket = [
        datablock for datablock in datablocks
        if client.stat_object(
            bucket=bucket,
            filename=f"{datablock.archiveId}",
        ) is None
    ]

    return datablocks_not_in_retrieval_bucket


@log
def reset_expiry_date(client: S3Storage, filenames: List[str], bucket: Bucket):

    retention_period = Variables().MINIO_URL_EXPIRATION_DAYS

    for filename in filenames:
        client.reset_expiry_date(
            bucket_name=bucket.name,
            filename=f"{filename}",
            retention_period_days=retention_period)


@log
def upload_objects_to_s3(
    client: S3Storage,
    prefix: Path,
    bucket: Bucket,
    source_folder: Path,
    ext: str | None = None,
    progress_callback: Callable[[float], None] = None
) -> List[Path]:
    uploaded_files: List[Path] = []

    files_to_upload = [f for f in source_folder.iterdir() if not ext or f.suffix == ext]

    total_files = len(files_to_upload)

    for filepath in files_to_upload:
        minio_path: Path = prefix / filepath.name
        client.fput_object(source_folder / filepath.name, minio_path, bucket)
        uploaded_files.append(filepath)
        if progress_callback is not None:
            progress_callback(1.0 * len(uploaded_files) / total_files)
    return uploaded_files


@log
def delete_objects_from_s3(client: S3Storage, prefix: Path, bucket: Bucket):
    getLogger().info(f"Cleaning up objects in {bucket.name}/{prefix}")
    client.delete_objects(minio_prefix=prefix, bucket=bucket)


@log
def create_datablock_entries(
    dataset_id: str,
    folder: Path,
    origDataBlocks: List[OrigDataBlock],
    tar_infos: List[ArchiveInfo],
    progress_callback: Callable[[float], None] = None
) -> List[DataBlock]:
    """Create datablock entries compliant with schema provided by scicat

    Args:
        dataset_id (str): Dataset identifier
        folder (Path): _description_
        origDataBlocks (List[OrigDataBlock]): _description_
        tarballs (List[Path]): _description_

    Returns:
        List[DataBlock]: _description_
    """

    version = 1.0

    datablocks: List[DataBlock] = []

    for idx, tar in enumerate(tar_infos):
        # TODO: is it necessary to use any datablock information?
        o = origDataBlocks[0]

        data_file_list: List[DataFile] = []

        tar_path = folder / tar.path

        tarball = tarfile.open(tar_path)

        for tar_info in tarball.getmembers():
            checksum = calculate_md5_checksum(
                StoragePaths.scratch_archival_raw_files_folder(dataset_id) / tar_info.path
            )

            data_file_list.append(
                DataFile(
                    path=tar_info.path,
                    size=tar_info.size,
                    chk=checksum,
                    uid=str(tar_info.uid),
                    gid=str(tar_info.gid),
                    perm=str(tar_info.mode),
                    time=str(datetime.datetime.now(datetime.UTC).isoformat()),
                )
            )

        datablocks.append(
            DataBlock(
                archiveId=str(StoragePaths.relative_datablocks_folder(dataset_id) / tar_path.name),
                size=tar.unpackedSize,
                packedSize=tar.packedSize,
                chkAlg="md5",
                version=str(version),
                dataFileList=data_file_list,
                rawDatasetId=o.rawdatasetId,
                derivedDatasetId=o.derivedDatasetId,
            )
        )

        if progress_callback:
            progress_callback((idx + 1) / len(tar_infos))

    return datablocks


@log
def find_object_in_s3(client: S3Storage, dataset_id, datablock_name):
    return datablock_name in (
        o.Name
        for o in list_datablocks(
            client,
            bucket=Bucket.staging_bucket(),
            prefix=StoragePaths.relative_datablocks_folder(dataset_id),
        )
    )


@log
def move_data_to_LTS(dataset_id: str, datablock: DataBlock):
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    datablock_name = datablock.archiveId

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name

    if not datablock_full_path.exists():
        raise DatasetError(
            f"Datablock {datablock_name} not found in storage at {StoragePaths.relative_datablocks_folder(dataset_id)}"
        )

    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    lts_target_dir.mkdir(parents=True, exist_ok=True)

    getLogger().info("Copy datablock to LTS")

    # Copy to LTS
    copy_file_to_folder(src_file=datablock_full_path.absolute(), dst_folder=lts_target_dir.absolute())


@log
def copy_file_from_LTS(dataset_id: str, datablock: DataBlock):
    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    datablock_name = Path(datablock.archiveId).name

    lts_datablock_path = lts_target_dir / datablock_name

    asyncio.run(
        wait_for_file_accessible(lts_datablock_path.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S)
    )

    # Copy back from LTS to scratch
    verification_path = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    verification_path.mkdir(exist_ok=True)
    copy_file_to_folder(src_file=lts_datablock_path, dst_folder=verification_path)


@log
def verify_checksum(dataset_id: str, datablock: DataBlock, expected_checksum: str) -> None:
    datablock_name = Path(datablock.archiveId).name
    verification_path = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    datablock_checksum = calculate_md5_checksum(verification_path / datablock_name)

    if datablock_checksum != expected_checksum:
        raise SystemError(
            f"Datablock verification failed. Expected: {expected_checksum},  got: {datablock_checksum}"
        )


@log
def copy_file_to_folder(src_file: Path, dst_folder: Path):
    """Copies a file to a destination folder (does not need to exist)

    Args:
        src_file (Path): Source file
        dst_folder (Path): destination folder - needs to exist

    Raises:
        SystemError: raises if operation fails
    """
    if not src_file.exists() or not src_file.is_file():
        raise SystemError(f"Source file {src_file} is not a file or does not exist")
    if dst_folder.is_file():
        raise SystemError(f"Destination folder {dst_folder} is not a folder")

    getLogger().info(f"Start Copy operation. src:{src_file}, dst{dst_folder}")

    with subprocess.Popen(
        ["rsync",
         "-rcvh",  # r: recursive, c: checksum, v: verbose, h: human readable format
         "--stats",  # file transfer stats
         "--no-perms",  # don't preserve the file permissions of the source files
         "--no-owner",  # don't preserve the owner
         "--no-group",  # don't preserve the group ownership
         "--mkpath", str(src_file), str(dst_folder)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    ) as popen:
        for line in popen.stdout:
            getLogger().info(line)

        popen.stdout.close()
        return_code = popen.wait()
        getLogger().info(f"Finished with return code : {return_code}")

        expected_dst_file = dst_folder / src_file.name

    if not expected_dst_file.exists():
        raise SystemError(f"Copying did not produce file {expected_dst_file}")


@log
def verify_datablock_content(datablock: DataBlock, datablock_path: str):

    expected_checksums: Dict[str, str] = {
        datafile.path: datafile.chk or "" for datafile in datablock.dataFileList or []
    }

    try:
        tar: tarfile.TarFile = tarfile.open(datablock_path, "r")
    except Exception as e:
        raise SystemError(f"Failed to read datablock {datablock.archiveId}: {e}")

    for file in tar.getmembers():
        extracted = tar.extractfile(file)
        if extracted is None:
            raise SystemError(f"Member {file} not found in {tar}")

        # TODO: add other algorithms
        assert datablock.chkAlg == "md5"

        checksum = hashlib.file_digest(extracted, "md5").hexdigest()  # type: ignore
        expected_checksum = expected_checksums.get(file.path, "")

        if expected_checksum != checksum:
            raise SystemError(
                f"Datablock verification failed: expected checksum {expected_checksum} but got actual {checksum} for {file}"
            )


@log
def cleanup_lts_folder(dataset_id: str) -> None:
    lts_folder = StoragePaths.lts_datablocks_folder(dataset_id)
    shutil.rmtree(lts_folder, ignore_errors=True)


@log
def cleanup_s3_staging(client: S3Storage, dataset_id: str) -> None:
    delete_objects_from_s3(
        client,
        prefix=StoragePaths.relative_datablocks_folder(dataset_id),
        bucket=Bucket.staging_bucket(),
    )


@log
def cleanup_s3_retrieval(client: S3Storage, dataset_id: str) -> None:
    delete_objects_from_s3(
        client,
        prefix=StoragePaths.relative_datablocks_folder(dataset_id),
        bucket=Bucket.retrieval_bucket(),
    )


@log
def cleanup_s3_landingzone(client: S3Storage, dataset_id: str) -> None:
    delete_objects_from_s3(
        client,
        prefix=StoragePaths.relative_raw_files_folder(dataset_id),
        bucket=Bucket.landingzone_bucket(),
    )


@log
def verify_objects(
    client: S3Storage,
    uploaded_objects: List[Path],
    minio_prefix: Path,
    bucket: Bucket,
) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not client.stat_object(filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


def on_rmtree_error(func, path, _):
    getLogger().error(f"Failed to remove: {path}")


@log
def cleanup_scratch(dataset_id: str):
    getLogger().info(f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")
    shutil.rmtree(StoragePaths.scratch_folder(dataset_id), ignore_errors=True, onerror=on_rmtree_error)


@log
def sufficient_free_space_on_lts():
    """Checks for free space on configured LTS storage with respect to configured free space percentage.

    Returns:
        boolean: condition of eneough free space satisfied
    """

    path = Variables().LTS_STORAGE_ROOT
    stat = shutil.disk_usage(path)
    free_percentage = 100.0 * stat.free / stat.total
    getLogger().info(
        f"LTS free space:{free_percentage:.2}%, expected: {Variables().LTS_FREE_SPACE_PERCENTAGE:.2}%"
    )
    return free_percentage >= Variables().LTS_FREE_SPACE_PERCENTAGE


@log
async def wait_for_free_space():
    """Asynchronous wait until there is enough free space. Waits in linear intervals to check for free space

        TODO: add exponential backoff for waiting time

    Returns:
        boolean: Returns True once there is enough free space
    """
    while not sufficient_free_space_on_lts():
        seconds_to_wait = 30
        getLogger().info(f"Not enough free space. Waiting for {seconds_to_wait}s")
        await asyncio.sleep(seconds_to_wait)

    return True


@log
async def wait_for_file_accessible(file: Path, timeout_s=360):
    """
    Returns:
    """
    total_time_waited_s = 0
    while not os.access(path=file, mode=os.R_OK):
        seconds_to_wait = 30
        getLogger().info(f"File {file} currently not available. Trying again in {seconds_to_wait} seconds.")
        await asyncio.sleep(seconds_to_wait)
        total_time_waited_s += seconds_to_wait
        if total_time_waited_s > timeout_s:
            raise SystemError(f"File f{file} was not accessible within {timeout_s} seconds")

    getLogger().info(f"File {file} accessible.")

    return True


@log
def get_datablock_path_in_LTS(datablock: DataBlock) -> Path:
    datablock_in_lts = Variables().LTS_STORAGE_ROOT / datablock.archiveId

    if not datablock_in_lts.exists():
        raise SystemError(f"Datablock {datablock.id} does not exist at {datablock.archiveId} in LTS")

    return datablock_in_lts


@log
def upload_datablock(client: S3Storage, file: Path, datablock: DataBlock):
    # upload to s3 retrieval bucket
    client.fput_object(
        source_file=file,
        destination_file=Path(datablock.archiveId),
        bucket=Bucket.retrieval_bucket(),
    )


@log
def copy_from_LTS_to_scratch_retrieval(dataset_id: str, datablock: DataBlock) -> None:
    datablock_in_lts = get_datablock_path_in_LTS(datablock)

    # copy to local folder
    scratch_destination_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    scratch_destination_folder.mkdir(exist_ok=True, parents=True)

    asyncio.run(
        wait_for_file_accessible(datablock_in_lts.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S)
    )

    copy_file_to_folder(src_file=datablock_in_lts, dst_folder=scratch_destination_folder)


@log
def verify_datablock_in_verification(dataset_id: str, datablock: DataBlock) -> None:
    datablock_name = Path(datablock.archiveId).name
    verification_path = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    datablock_path = verification_path / datablock_name
    verify_datablock_content(datablock=datablock, datablock_path=datablock_path)


@log
def verify_datablock_on_scratch(dataset_id: str, datablock: DataBlock) -> None:
    scratch_destination_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    assert scratch_destination_folder.exists()
    datablock_on_scratch = scratch_destination_folder / Path(datablock.archiveId).name
    verify_datablock_content(datablock=datablock, datablock_path=datablock_on_scratch)


@log
def upload_data_to_retrieval_bucket(client: S3Storage, dataset_id: str, datablock: DataBlock) -> None:
    scratch_destination_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    assert scratch_destination_folder.exists()
    datablock_on_scratch = scratch_destination_folder / Path(datablock.archiveId).name
    upload_datablock(client=client, file=datablock_on_scratch, datablock=datablock)
