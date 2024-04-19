import tarfile
import os
import requests
from uuid import uuid4
from typing import List

from pathlib import Path

from .working_storage_interface import minioClient, Bucket
from .model import OrigDataBlock, DataBlock, DataFile

_SCRATCH_FOLDER = Path(os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch"))


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
    print(f"Minio: {minioClient._URL}")
    return minioClient.get_objects(minio_prefix, bucket)


def download_objects(minio_prefix: str, bucket: Bucket, destination_folder: Path) -> List[Path]:

    if not destination_folder.exists():
        raise FileNotFoundError(f"Destination folder {destination_folder} not reachable")

    files: List[Path] = []

    for object in minioClient.get_objects(minio_prefix, bucket):
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


def upload_objects(minio_prefix: Path, bucket: Bucket, source_folder: Path) -> List[Path]:
    uploaded_files: List[Path] = []
    for filepath in (f for f in source_folder.iterdir() if f.suffix == ".gz"):
        minio_path: Path = minio_prefix / filepath.name
        minioClient.put_object(source_folder / filepath, minio_path, bucket)
        uploaded_files.append(filepath)
    return uploaded_files


def delete_objects(minio_prefix: str, bucket: Bucket):
    print(f"Cleaning up objects in {bucket.name}/{minio_prefix}")
    pass


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


def validate_data_in_LTS(datablocks: List[DataBlock]) -> None:
    pass


def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    print(f"Creating datablocks for {dataset_id}")

    if len(origDataBlocks) == 0:
        return []

    if all(False for _ in find_objects(str(dataset_id), minioClient.LANDINGZONE_BUCKET)):
        raise Exception(f"No objects found for dataset {dataset_id}")

    scratch_folder = _SCRATCH_FOLDER / "archival" / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    file_paths = download_objects(minio_prefix=str(dataset_id), bucket=minioClient.LANDINGZONE_BUCKET,
                                  destination_folder=_SCRATCH_FOLDER / "archival")

    print(f"Downloaded {len(file_paths)} objects from {minioClient.LANDINGZONE_BUCKET}")

    tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    print(f"Created {len(tarballs)} datablocks from {len(file_paths)} objects")

    datablocks = create_datablock_entries(dataset_id, scratch_folder, origDataBlocks, tarballs)

    uploaded_objects = upload_objects(minio_prefix=str(dataset_id), bucket=minioClient.ARCHIVAL_BUCKET,
                                      source_folder=scratch_folder)

    missing_objects = verify_objects(uploaded_objects, minio_prefix=str(dataset_id), bucket=minioClient.ARCHIVAL_BUCKET,
                                     source_folder=scratch_folder)

    if len(missing_objects) > 0:
        raise Exception(f"{len(missing_objects)} datablocks missing")

    # regular cleanup
    delete_objects(minio_prefix=str(dataset_id), bucket=minioClient.LANDINGZONE_BUCKET)
    delete_scratch_folder(dataset_id, "archival")

    return datablocks


def verify_objects(uploaded_objects: List[Path],
                   minio_prefix: str, bucket: Bucket, source_folder: Path) -> List[Path]:
    missing_files: List[Path] = []
    for f in uploaded_objects:
        if not minioClient.stat_object(
                filename=str(f), bucket=bucket):
            missing_files.append(f)
    return missing_files


def delete_scratch_folder(dataset_id: int, folder_type: str):
    if folder_type not in ["archival", "retrieval"]:
        raise Exception(f"No valid folder_type to delete: {folder_type}")
    scratch_folder = _SCRATCH_FOLDER / folder_type / str(dataset_id)
    # import shutil
    # shutil.rmtree(scratch_folder)


def create_dummy_dataset(dataset_id: int):
    scratch_folder = _SCRATCH_FOLDER / str(dataset_id)
    if scratch_folder.exists():
        scratch_folder.mkdir()

    for i in range(10):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs=64M count=2 iflag=fullblock")

    upload_objects(minio_prefix=str(dataset_id), bucket=minioClient.LANDINGZONE_BUCKET,
                   source_folder=scratch_folder)


__all__ = [
    "create_datablocks",
    "move_data_to_staging",
    "move_data_to_LTS",
    "validate_data_in_LTS",
    "create_dummy_dataset",
    "delete_scratch_folder"
]
