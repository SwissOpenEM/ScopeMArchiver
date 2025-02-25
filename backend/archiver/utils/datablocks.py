from dataclasses import dataclass
import subprocess
import tarfile
import os
import shutil
import asyncio
import time
import datetime
import hashlib

from typing import Dict, List
from pathlib import Path

from archiver.utils.s3_storage_interface import S3Storage, Bucket
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.utils.log import getLogger, log
from archiver.config.variables import Variables
from archiver.flows.utils import DatasetError, SystemError, StoragePaths


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
class TarInfo:
    unpackedSize: int
    packedSize: int
    path: Path


@log
def create_tarballs(
    dataset_id: str,
    src_folder: Path,
    dst_folder: Path,
    target_size: int = 300 * (1024**2),
) -> List[TarInfo]:
    """Create datablocks, i.e. .tar.gz files, from files in a folder. The files will be named according to
    the dataset they belong to. The target size of the created files is 300 MB by default

    Args:
        dataset_id (str):
        folder (Path): _description_
        target_size (int, optional): _description_. Defaults to 300*(1024**2).

    Returns:
        List[Path]: _description_
    """

    # TODO: corner case: target size < file size
    tarballs: List[TarInfo] = []
    tar_name = dataset_id.replace("/", "--")

    current_tar_info = TarInfo(
        unpackedSize=0,
        packedSize=0,
        path=Path(dst_folder / Path(f"{tar_name}_{len(tarballs)}.tar.gz")),
    )

    current_tarfile: tarfile.TarFile = tarfile.open(current_tar_info.path, "w")

    if not any(Path(src_folder).iterdir()):
        raise SystemError(f"Empty folder {src_folder} found.")

    for file in src_folder.iterdir():
        if file.stat().st_size > target_size:
            raise SystemError(
                f"Size of {file} is larger than target size {target_size}. Increase target_size."
            )
        if current_tar_info.path.stat().st_size + file.stat().st_size > target_size:
            current_tar_info.packedSize = current_tar_info.path.stat().st_size
            current_tarfile.close()
            tarballs.append(current_tar_info)

            current_tar_info = TarInfo(
                unpackedSize=0,
                packedSize=0,
                path=Path(dst_folder / Path(f"{tar_name}_{len(tarballs)}.tar.gz")),
            )
            current_tarfile = tarfile.open(current_tar_info.path, "w")

        current_tar_info.unpackedSize += file.stat().st_size
        current_tarfile.add(name=file, arcname=file.name, recursive=False)

    current_tar_info.packedSize = current_tar_info.path.stat().st_size
    current_tarfile.close()
    tarballs.append(current_tar_info)

    return tarballs


@log
def calculate_md5_checksum(filename: Path, chunksize: int = 1024 * 1025) -> str:
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


@log
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
    client: S3Storage, prefix: Path, bucket: Bucket, destination_folder: Path
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

    files: List[Path] = []

    for item in client.list_objects(bucket, str(prefix)):
        item_name = Path(item.Name).name
        local_filepath = destination_folder / item_name
        local_filepath.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(
            bucket=bucket,
            folder=str(prefix),
            object_name=item.Name,
            target_path=local_filepath,
        )
        files.append(local_filepath)

    if len(files) == 0:
        raise SystemError(f"No files found in bucket {bucket} at {prefix}")

    return files


@log
def upload_objects_to_s3(
    client: S3Storage,
    prefix: Path,
    bucket: Bucket,
    source_folder: Path,
    ext: str | None = None,
) -> List[Path]:
    uploaded_files: List[Path] = []
    for filepath in (f for f in source_folder.iterdir() if not ext or f.suffix == ext):
        minio_path: Path = prefix / filepath.name
        client.fput_object(source_folder / filepath.name, minio_path, bucket)
        uploaded_files.append(filepath)
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
    tar_infos: List[TarInfo],
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
    for tar in tar_infos:
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
def move_data_to_LTS(client: S3Storage, dataset_id: str, datablock: DataBlock):
    # mount target dir and check access
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    datablock_name = datablock.archiveId

    getLogger().info(f"Searching datablock {datablock_name}")

    object_found = find_object_in_s3(client, dataset_id, datablock_name)

    if not object_found:
        raise DatasetError(
            f"Datablock {datablock_name} not found in storage at {StoragePaths.relative_datablocks_folder(dataset_id)}"
        )

    getLogger().info(f"Downloading datablock {datablock_name}")

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name

    download_object_from_s3(
        client,
        bucket=Bucket.staging_bucket(),
        folder=StoragePaths.relative_datablocks_folder(dataset_id),
        object_name=str(StoragePaths.relative_datablocks_folder(dataset_id) / datablock_name),
        target_path=datablock_full_path,
    )

    getLogger().info("Calculating Checksum.")
    checksum_source = calculate_md5_checksum(datablock_full_path)

    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    lts_target_dir.mkdir(parents=True, exist_ok=True)

    getLogger().info("Copy datablock to LTS")

    # Copy to LTS
    copy_file_to_folder(src_file=datablock_full_path.absolute(), dst_folder=lts_target_dir.absolute())

    # Wait before recalling the file for checksum verification
    time.sleep(10)

    destination = lts_target_dir / datablock_name

    getLogger().info("Verifying checksum")

    # Copy back from LTS to scratch
    verification_path = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    verification_path.mkdir(exist_ok=True)
    copy_file_to_folder(src_file=destination, dst_folder=verification_path)
    checksum_destination = calculate_md5_checksum(verification_path / datablock_name)

    if checksum_destination != checksum_source:
        raise SystemError("Datablock verification failed")


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
        ["rsync", "-rcvz", "--stats", "--mkpath", str(src_file), str(dst_folder)],
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
def verify_data_in_LTS(dataset_id: str, datablock: DataBlock) -> None:
    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_folder = datablocks_scratch_folder / Path(datablock.archiveId).name

    lts_datablock_path = StoragePaths.lts_datablocks_folder(dataset_id) / Path(datablock.archiveId).name

    asyncio.run(
        wait_for_file_accessible(lts_datablock_path.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S)
    )

    copy_file_to_folder(
        src_file=lts_datablock_path.absolute(),
        dst_folder=datablocks_scratch_folder.absolute(),
    )

    verify_datablock(datablock, datablock_folder)

    os.remove(datablock_folder)


@log
def verify_datablock(datablock: DataBlock, datablock_path: Path):
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
def create_datablocks(
    s3_client: S3Storage, dataset_id: str, origDataBlocks: List[OrigDataBlock]
) -> List[DataBlock]:
    if len(origDataBlocks) == 0:
        return []

    if all(
        False
        for _ in list_datablocks(
            s3_client,
            StoragePaths.relative_raw_files_folder(dataset_id),
            Bucket.landingzone_bucket(),
        )
    ):
        raise Exception(
            f"""No objects found in landing zone at {
                StoragePaths.relative_raw_files_folder(dataset_id)
            } for dataset {dataset_id}. Storage endpoint: {s3_client.url}"""
        )

    raw_files_scratch_folder = StoragePaths.scratch_archival_raw_files_folder(dataset_id)
    raw_files_scratch_folder.mkdir(parents=True, exist_ok=True)

    # files with full path are downloaded to scratch root
    file_paths = download_objects_from_s3(
        s3_client,
        prefix=StoragePaths.relative_raw_files_folder(dataset_id),
        bucket=Bucket.landingzone_bucket(),
        destination_folder=raw_files_scratch_folder,
    )

    getLogger().info(f"Downloaded {len(file_paths)} objects from {Bucket.landingzone_bucket()}")

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    tar_infos = create_tarballs(
        dataset_id=dataset_id,
        src_folder=raw_files_scratch_folder,
        dst_folder=datablocks_scratch_folder,
        target_size=Variables().ARCHIVER_TARGET_SIZE_MB * 1024 * 1024,
    )

    getLogger().info(f"Created {len(tar_infos)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(
        dataset_id,
        StoragePaths.scratch_archival_datablocks_folder(dataset_id),
        origDataBlocks,
        tar_infos,
    )

    uploaded_objects = upload_objects_to_s3(
        s3_client,
        prefix=StoragePaths.relative_datablocks_folder(dataset_id),
        bucket=Bucket.staging_bucket(),
        source_folder=datablocks_scratch_folder,
        ext=".gz",
    )

    missing_objects = verify_objects(
        s3_client,
        uploaded_objects,
        minio_prefix=StoragePaths.relative_datablocks_folder(dataset_id),
        bucket=Bucket.staging_bucket(),
        source_folder=datablocks_scratch_folder,
    )

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    return datablocks


@log
def cleanup_lts_folder(dataset_id: str) -> None:
    # TODO: is deletion possible?
    lts_folder = StoragePaths.lts_datablocks_folder(dataset_id)

    import random
    import string

    suffix = "".join(random.choice(string.ascii_uppercase) for _ in range(6))

    lts_folder_new = lts_folder.rename(str(lts_folder) + "_failed_" + suffix)
    getLogger().info(f"Move LTS folder from {lts_folder} to {lts_folder_new}")


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
    source_folder: Path,
) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not client.stat_object(filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


@log
def cleanup_scratch(dataset_id: str):
    getLogger().debug(f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")
    shutil.rmtree(StoragePaths.scratch_folder(dataset_id))

    getLogger().debug(f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")


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
        getLogger().info(f"File {file} currently not available. Try again in {seconds_to_wait} seconds.")
        await asyncio.sleep(seconds_to_wait)
        total_time_waited_s += seconds_to_wait
        if total_time_waited_s > timeout_s:
            raise SystemError(f"File f{file} was not accessible within {timeout_s} seconds")

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
def copy_from_LTS_to_retrieval(client: S3Storage, dataset_id: str, datablock: DataBlock):
    datablock_in_lts = get_datablock_path_in_LTS(datablock)

    # copy to local folder
    scratch_destination_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    scratch_destination_folder.mkdir(exist_ok=True, parents=True)

    asyncio.run(
        wait_for_file_accessible(datablock_in_lts.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S)
    )

    copy_file_to_folder(src_file=datablock_in_lts, dst_folder=scratch_destination_folder)

    # TODO: verify checksum
    # for each single file?
    getLogger().warning("Checksum verification missing!")
    file_on_scratch = scratch_destination_folder / Path(datablock.archiveId).name
    upload_datablock(client=client, file=file_on_scratch, datablock=datablock)
