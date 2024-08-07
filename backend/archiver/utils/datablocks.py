import subprocess
import tarfile
import os
import shutil
import asyncio
import time

from uuid import uuid4
from typing import Iterator, List
from pathlib import Path

from archiver.utils.working_storage_interface import S3Storage, Bucket
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


@log
def create_tarballs(dataset_id: int, src_folder: Path, dst_folder: Path,
                    target_size: int = 300 * (1024**2)) -> List[Path]:
    """ Create datablocks, i.e. .tar.gz files, from files in a folder. The files will be named according to
    the dataset they belong to. The target size of the created files is 300 MB by default

    Args:
        dataset_id (int):
        folder (Path): _description_
        target_size (int, optional): _description_. Defaults to 300*(1024**2).

    Returns:
        List[Path]: _description_
    """

    # TODO: corner case: target size < file size
    tarballs: List[Path] = []

    current_tar_file: Path = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
    filepath = dst_folder / current_tar_file

    tar = tarfile.open(filepath, 'x:gz', compresslevel=4)

    if not any(Path(src_folder).iterdir()):
        raise SystemError(f"Empty folder {src_folder} found.")

    for file in src_folder.iterdir():
        tar.add(name=file, arcname=file.name, recursive=False)

        if filepath.stat().st_size >= target_size:
            tar.close()
            tarballs.append(current_tar_file)
            current_tar_file = Path(f"{dataset_id}_{len(tarballs)}.tar.gz")
            filepath = dst_folder / current_tar_file
            tar = tarfile.open(filepath, 'w')

    tar.close()
    tarballs.append(current_tar_file)

    return tarballs


@log
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


@log
def download_object_from_s3(bucket: Bucket, folder: Path, object_name: str, target_path: Path):
    """Download an object from S3 storage.

    Args:
        bucket (Bucket): Bucket to look for file
        folder (Path): s3 prefix for object
        object_name (str): object name, no prefix
        target_path (Path): absolute or relative path for the file to be created
    """
    S3Storage().fget_object(bucket=bucket, folder=str(folder),
                            object_name=object_name, target_path=target_path)


@log
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


@log
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
        S3Storage().fget_object(bucket=bucket, folder=str(prefix),
                                object_name=item.object_name or "", target_path=local_filepath)
        files.append(local_filepath)

    if len(files) == 0:
        raise SystemError(f"No files found in bucket {bucket} at {prefix}")

    return files


@log
def upload_objects_to_s3(prefix: Path, bucket: Bucket, source_folder: Path, ext: str | None = None) -> List[Path]:
    uploaded_files: List[Path] = []
    for filepath in (f for f in source_folder.iterdir() if not ext or f.suffix == ext):
        minio_path: Path = prefix / filepath.name
        S3Storage().fput_object(source_folder / filepath.name, minio_path, bucket)
        uploaded_files.append(filepath)
    return uploaded_files


@log
def delete_objects_from_s3(prefix: Path, bucket: Bucket):
    getLogger().info(f"Cleaning up objects in {bucket.name}/{prefix}")
    S3Storage().delete_object(minio_prefix=prefix, bucket=bucket)


@log
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
            archiveId=str(StoragePaths.relative_datablocks_folder(
                dataset_id) / tar_path.name),
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


@log
def find_object_in_s3(dataset_id, datablock_name):
    object_found = next((x
                         for x in list_s3_objects(
                             prefix=StoragePaths.relative_datablocks_folder(
                                 dataset_id),
                             bucket=Bucket.staging_bucket()) if x.object_name == datablock_name),
                        False)

    return object_found


@log
def move_data_to_LTS(dataset_id: int, datablock: DataBlock) -> str:

    # mount target dir and check access
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(
            f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    datablock_name = datablock.archiveId

    getLogger().info(f"Searching datablock {datablock_name}")

    object_found = find_object_in_s3(dataset_id, datablock_name)

    if not object_found:
        raise DatasetError(
            f"Datablock {datablock_name} not found in storage at {StoragePaths.relative_datablocks_folder(dataset_id)}")

    getLogger().info(f"Downloading datablock {datablock_name}")

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(
        dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name

    download_object_from_s3(bucket=Bucket.staging_bucket(), folder=StoragePaths.relative_datablocks_folder(
        dataset_id), object_name=str(StoragePaths.relative_datablocks_folder(dataset_id) / datablock_name), target_path=datablock_full_path)

    getLogger().info("Calculating Checksum.")
    checksum_hash_source = calculate_checksum(datablock_full_path)

    # TODO: Compare checksum against entry in datablock

    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    lts_target_dir.mkdir(parents=True, exist_ok=True)

    getLogger().info("Copy datablock to LTS")

    # Copy to LTS
    copy_file_to_folder(src_file=datablock_full_path.absolute(),
                        dst_folder=lts_target_dir.absolute())

    # Wait before recalling the file for checksum verification
    time.sleep(10)

    destination = lts_target_dir / datablock_name

    getLogger().info("Verifying checksum")
    # Copy back from LTS to scratch
    # TODO: can this run in parallel like this? Or is this also limited by the LTS?
    verification_path = StoragePaths.scratch_archival_datablocks_folder(dataset_id) / "verification"
    verification_path.mkdir(exist_ok=True)
    copy_file_to_folder(src_file=destination, dst_folder=verification_path)
    checksum_destination = calculate_checksum(verification_path / datablock_name)

    if checksum_destination != checksum_hash_source:
        raise SystemError("Datablock verification failed")

    return checksum_hash_source


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

    with subprocess.Popen(["rsync", "-rcvz", "--stats", "--mkpath",
                          str(src_file), str(dst_folder)],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          universal_newlines=True) as popen:

        for line in popen.stdout:
            getLogger().info(line)

        popen.stdout.close()
        return_code = popen.wait()
        getLogger().info(f"Finished with return code : {return_code}")

        expected_dst_file = dst_folder / src_file.name

    if not expected_dst_file.exists():
        raise SystemError(f"Copying did not produce file {expected_dst_file}")


@log
def verify_data_in_LTS(dataset_id: int, datablock: DataBlock, expected_checksum: str) -> None:

    dst_folder = StoragePaths.scratch_archival_datablocks_folder(
        dataset_id) / "verification"
    dst_folder.mkdir(parents=True, exist_ok=True)
    local_datablock_path = dst_folder / Path(datablock.archiveId).name

    lts_datablock_path = StoragePaths.lts_datablocks_folder(
        dataset_id) / Path(datablock.archiveId).name

    asyncio.run(wait_for_file_accessible(lts_datablock_path.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S))

    copy_file_to_folder(src_file=lts_datablock_path.absolute(), dst_folder=dst_folder.absolute())

    checksum = calculate_checksum(local_datablock_path)

    if checksum != expected_checksum:
        raise SystemError(
            f"Datablock verification failed: expected checksum {expected_checksum} but got actual {checksum}")

    os.remove(local_datablock_path)


@log
def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    getLogger().info(f"Creating datablocks for {dataset_id}")

    if len(origDataBlocks) == 0:
        return []

    if all(False for _ in list_s3_objects(StoragePaths.relative_origdatablocks_folder(dataset_id), Bucket.landingzone_bucket())):
        raise Exception(
            f"No objects found in landing zone at {StoragePaths.relative_datablocks_folder(dataset_id)} for dataset {dataset_id}. Storage endpoint: {S3Storage().url}")

    # files with full path are downloaded to scratch root
    file_paths = download_objects_from_s3(prefix=StoragePaths.relative_origdatablocks_folder(
        dataset_id), bucket=Bucket.landingzone_bucket(), destination_folder=StoragePaths.scratch_archival_root())

    getLogger().info(
        f"Downloaded {len(file_paths)} objects from {Bucket.landingzone_bucket()}")

    origdatablocks_scratch_folder = StoragePaths.scratch_archival_origdatablocks_folder(dataset_id)
    origdatablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    raw_files_scratch_folder = StoragePaths.scratch_archival_files_folder(dataset_id)
    raw_files_scratch_folder.mkdir(parents=True, exist_ok=True)

    unpack_tarballs(origdatablocks_scratch_folder, raw_files_scratch_folder)

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    tarballs = create_tarballs(
        dataset_id=dataset_id,
        src_folder=raw_files_scratch_folder,
        dst_folder=datablocks_scratch_folder,
        target_size=Variables().ARCHIVER_TARGET_SIZE_MB * 1024 * 1024
    )

    getLogger().info(
        f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(
        dataset_id, StoragePaths.scratch_archival_datablocks_folder(dataset_id), origDataBlocks, tarballs)

    uploaded_objects = upload_objects_to_s3(prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=Bucket.staging_bucket(), source_folder=datablocks_scratch_folder, ext=".gz")

    missing_objects = verify_objects(uploaded_objects, minio_prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=Bucket.staging_bucket(), source_folder=datablocks_scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    return datablocks


@log
def cleanup_lts_folder(dataset_id: int) -> None:
    # TODO: is deletion possible?
    lts_folder = StoragePaths.lts_datablocks_folder(dataset_id)

    import random
    import string
    suffix = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))

    lts_folder_new = lts_folder.rename(str(lts_folder) + "_failed_" + suffix)
    getLogger().info(f"Move LTS folder from {lts_folder} to {lts_folder_new}")


@log
def cleanup_s3_staging(dataset_id: int) -> None:
    delete_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                           bucket=Bucket.staging_bucket())


@log
def cleanup_s3_retrieval(dataset_id: int) -> None:
    delete_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                           bucket=Bucket.retrieval_bucket())


@log
def cleanup_s3_landingzone(dataset_id: int) -> None:
    delete_objects_from_s3(prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                           bucket=Bucket.landingzone_bucket())


@log
def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not S3Storage().stat_object(
                filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


@log
def cleanup_scratch(dataset_id: int):
    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")
    shutil.rmtree(StoragePaths.scratch_folder(dataset_id))

    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")


@log
def sufficient_free_space_on_lts():
    """ Checks for free space on configured LTS storage with respect to configured free space percentage.

    Returns:
        boolean: condition of eneough free space satisfied
    """

    path = Variables().LTS_STORAGE_ROOT
    stat = shutil.disk_usage(path)
    free_percentage = 100.0 * stat.free / stat.total
    getLogger().info(f"LTS free space:{free_percentage:.2}%, expected: {Variables().LTS_FREE_SPACE_PERCENTAGE:.2}%")
    return free_percentage >= Variables().LTS_FREE_SPACE_PERCENTAGE


@log
async def wait_for_free_space():
    """ Asynchronous wait until there is enough free space. Waits in linear intervals to check for free space

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
        boolean: Returns True once there is enough free space
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
def upload_datablock(file: Path, datablock: DataBlock):
    # upload to s3 retrieval bucket
    S3Storage().fput_object(source_file=file,
                            destination_file=Path(datablock.archiveId),
                            bucket=Bucket.retrieval_bucket())


@log
def copy_from_LTS_to_retrieval(dataset_id: int, datablock: DataBlock):

    datablock_in_lts = get_datablock_path_in_LTS(datablock)

    # copy to local folder
    scratch_destination_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    scratch_destination_folder.mkdir(exist_ok=True, parents=True)

    asyncio.run(wait_for_file_accessible(datablock_in_lts.absolute(), Variables().ARCHIVER_LTS_FILE_TIMEOUT_S))

    copy_file_to_folder(src_file=datablock_in_lts, dst_folder=scratch_destination_folder)

    # TODO: verify checksum
    # for each single file?
    getLogger().warning("Checksum verification missing!")
    file_on_scratch = scratch_destination_folder / Path(datablock.archiveId).name
    upload_datablock(file=file_on_scratch, datablock=datablock)


@log
def create_presigned_urls(datablocks: List[DataBlock]) -> List[str]:
    urls = []
    for d in datablocks:
        urls.append(S3Storage().get_presigned_url(Bucket.retrieval_bucket(), d.archiveId))
    return urls
