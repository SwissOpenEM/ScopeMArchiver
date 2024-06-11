import subprocess
import tarfile
import shutil
from uuid import uuid4
from typing import List

from pathlib import Path

from archiver.utils.working_storage_interface import MinioStorage, Bucket
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.utils.log import getLogger
from archiver.config.variables import Variables
from archiver.flows.utils import DatasetError, SystemError, StoragePaths


def create_tarballs(dataset_id: int, folder: Path,
                    target_size: int = 300 * (1024**2)) -> List[Path]:
    """Create tar archives from files found in folder"""

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


def calculate_checksum(filename, chunksize=1024 * 1025) -> str:
    import hashlib
    m = hashlib.md5()
    with open(filename, 'rb') as f:
        while chunk := f.read(chunksize):
            m.update(chunk)
    return m.hexdigest()


def download_object(bucket: Bucket, folder: Path, object_name: str, target_path: Path):
    MinioStorage().get_object(bucket=bucket, folder=str(folder), object_name=object_name, target_path=target_path)


def find_objects(minio_prefix: Path, bucket: Bucket):
    getLogger().debug(f"Minio: {MinioStorage().url}")
    return MinioStorage().list_objects(bucket, str(minio_prefix))


def download_objects(minio_prefix: Path, bucket: Bucket, destination_folder: Path) -> List[Path]:

    if not destination_folder.exists():
        raise FileNotFoundError(
            f"Destination folder {destination_folder} not reachable")

    files: List[Path] = []

    for item in MinioStorage().list_objects(bucket, str(minio_prefix)):
        local_filepath = destination_folder / Path(item.object_name or "")
        local_filepath.parent.mkdir(parents=True, exist_ok=True)
        MinioStorage().get_object(bucket=bucket, folder=str(minio_prefix), object_name=item.object_name or "", target_path=local_filepath)
        files.append(local_filepath)

    # for object in MinioStorage().list_objects(bucket, str(minio_prefix)):
    #     object_name = object.object_name if object.object_name is not None else ""
    #     presigned_url = MinioStorage().get_presigned_url(
    #         filename=object_name, bucket=bucket)
    #     stat = MinioStorage().stat_object(
    #         filename=object_name, bucket=bucket)

    #     with requests.get(presigned_url, stream=True) as r:
    #         r.raise_for_status()
    #         chunk_size = 8192
    #         with open(local_filepath, 'wb') as f:
    #             for chunk in r.iter_content(chunk_size=chunk_size):
    #                 f.write(chunk)
    #     files.append(local_filepath)
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


def verify(datablock: DataBlock, file_path: Path):
    pass


def move_data_to_LTS(dataset_id: int, datablock: DataBlock) -> str:

    # mount target dir and check access
    if not Variables().LTS_STORAGE_ROOT.exists():
        raise FileNotFoundError(
            f"Can't open LTS root {Variables().LTS_STORAGE_ROOT}")

    # TODO: set permissions

    datablock_name = datablock.archiveId

    getLogger().info(f"Searching datablock {datablock_name}")
    # archive_ids: Set[str] = set(map(lambda d: d.archiveId, datablocks))
    # find objects
    object_found = next((x
                         for x in find_objects(
                             minio_prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                             bucket=MinioStorage().STAGING_BUCKET) if x.object_name == datablock_name),
                        False)
    if not object_found:
        raise DatasetError(f"Datablock {datablock_name} not found in storage at {StoragePaths.relative_datablocks_folder(dataset_id)}")

    getLogger().info(f"Downloading datablock {datablock_name}")
    # download to target dir
    datablocks_scratch_folder = StoragePaths.scratch_datablocks_folder(dataset_id)

    if not datablocks_scratch_folder.exists():
        datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    datablock_name = Path(datablock.archiveId).name
    datablock_full_path = datablocks_scratch_folder / datablock_name

    download_object(bucket=MinioStorage().STAGING_BUCKET, folder=StoragePaths.relative_datablocks_folder(
        dataset_id), object_name=str(StoragePaths.relative_datablocks_folder(dataset_id) / datablock_name), target_path=datablock_full_path)

    getLogger().info(f"Calculate Checksum")
    checksum_hash_source = calculate_checksum(datablock_full_path)

    # if not verify(datablock, datablock_full_path):
    #     raise SystemError("Verification failed")

    lts_target_dir = StoragePaths.lts_datablocks_folder(dataset_id)
    lts_target_dir.mkdir(parents=True, exist_ok=True)

    getLogger().info("Copy datablock")
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

    shutil.rmtree(local_datablock_path)


def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    getLogger().info(f"Creating datablocks for {dataset_id}")

    if len(origDataBlocks) == 0:
        return []

    if all(False for _ in find_objects(StoragePaths.relative_datablocks_folder(dataset_id), MinioStorage().LANDINGZONE_BUCKET)):
        raise Exception(
            f"No objects found in landing zone at {StoragePaths.relative_datablocks_folder(dataset_id)} for dataset {dataset_id}. Storage endpoint: {MinioStorage().url}")

    dataset_scratch_folder = StoragePaths.scratch_folder(dataset_id)

    # import shutil
    # shutil.rmtree(dataset_scratch_folder)

    dataset_scratch_folder.mkdir(parents=True, exist_ok=True)

    # files with full path are downloaded to scratch root
    file_paths = download_objects(minio_prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=MinioStorage().LANDINGZONE_BUCKET, destination_folder=StoragePaths.scratch_root())

    getLogger().info(
        f"Downloaded {len(file_paths)} objects from {MinioStorage().LANDINGZONE_BUCKET}")

    datablocks_scratch_folder = StoragePaths.scratch_datablocks_folder(dataset_id)

    tarballs = create_tarballs(dataset_id=dataset_id, folder=datablocks_scratch_folder)

    getLogger().info(
        f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(
        dataset_id, StoragePaths.scratch_datablocks_folder(dataset_id), origDataBlocks, tarballs)

    uploaded_objects = upload_objects(minio_prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=MinioStorage().STAGING_BUCKET, source_folder=datablocks_scratch_folder, ext=".gz")

    missing_objects = verify_objects(uploaded_objects, minio_prefix=StoragePaths.relative_datablocks_folder(
        dataset_id), bucket=MinioStorage().STAGING_BUCKET, source_folder=datablocks_scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    # regular cleanup
    delete_objects(minio_prefix=Path(str(dataset_id)),
                   bucket=MinioStorage().LANDINGZONE_BUCKET)
    cleanup_scratch(dataset_id)

    return datablocks


def cleanup_lts_folder(dataset_id: int) -> None:
    lts_folder = StoragePaths.lts_datablocks_folder(dataset_id)

    # import shutil
    # shutil.rmtree(lts_folder, ignore_errors=True)


def cleanup_staging(dataset_id: int) -> None:
    delete_objects(minio_prefix=StoragePaths.relative_datablocks_folder(dataset_id),
                   bucket=MinioStorage().STAGING_BUCKET)


def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not MinioStorage().stat_object(
                filename=str(minio_prefix / f.name), bucket=bucket):
            missing_files.append(f)
    return missing_files


def cleanup_scratch(dataset_id: int):
    import shutil
    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_datablocks_folder(dataset_id)}")
    shutil.rmtree(StoragePaths.scratch_datablocks_folder(dataset_id))

    getLogger().debug(
        f"Cleaning up objects in scratch folder: {StoragePaths.scratch_folder(dataset_id)}")
    # shutil.rmtree(StoragePaths.scratch_datablocks_folder(dataset_id))

    # if folder_type not in ["archival", "retrieval"]:
    #     raise Exception(f"No valid folder_type to delete: {folder_type}")
    # scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / \
    #     folder_type / str(dataset_id)
    # getLogger().debug(
    #     f"Cleaning up objects in scratch folder: {scratch_folder}")

    # shutil.rmtree(scratch_folder)
    # for d in datablocks:
    #     for f in d.dataFileList or []:
    #         os.remove(f.path)
    #     os.remove(d.archiveId)


__all__ = [
    "create_datablocks",
    "move_data_to_LTS",
    "verify_data_in_LTS",
    "cleanup_scratch",
    "cleanup_staging",
]
