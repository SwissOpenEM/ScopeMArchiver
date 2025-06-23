import datetime
import shutil
import pytest
import os
import tarfile
from typing import List
from pathlib import Path
import tempfile
from unittest.mock import patch

from archiver.flows.tests.helpers import mock_s3client
from archiver.utils.datablocks import ArchiveInfo
import archiver.utils.datablocks as datablock_operations
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.flows.utils import StoragePaths, SystemError


test_dataset_id = "testprefix/1234.4567"
MB = 1024 * 1024


def create_raw_files_fixture(storage_paths_fixture, num_raw_files, file_size_in_bytes):
    prefix_folder = StoragePaths.scratch_archival_raw_files_folder(test_dataset_id)
    relative_subfolders = Path("subfolder1") / "subfolder2"
    folder = prefix_folder / relative_subfolders
    folder.mkdir(parents=True, exist_ok=True)
    for n in range(num_raw_files):
        filename = folder / f"img_{n}.png"
        with open(filename, "wb") as fout:
            print(f"Creating file {filename}")
            fout.write(os.urandom(file_size_in_bytes))
    return prefix_folder


@pytest.fixture()
def dst_folder_fixture(storage_paths_fixture):
    folder: Path = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)
    folder.mkdir(parents=True)
    return folder


FILE_SIZE = MB  # 1 MB files


@pytest.mark.parametrize(
    "target_size_in_bytes,num_raw_files,single_file_size_in_bytes,expected_num_compressed_files",
    [
        (2.5 * FILE_SIZE, 10, FILE_SIZE, 5),  # total size > target size
        (10 * FILE_SIZE, 10, FILE_SIZE, 1),  # total size == target size
        (11 * FILE_SIZE, 10, FILE_SIZE, 1),  # total size < target size
    ],
)
def test_create_archives(
    target_size_in_bytes: int,
    num_raw_files,
    single_file_size_in_bytes,
    expected_num_compressed_files,
    dst_folder_fixture: Path,
    storage_paths_fixture,
):
    raw_files_path = create_raw_files_fixture(storage_paths_fixture, num_raw_files, single_file_size_in_bytes)

    tar_infos = datablock_operations.create_tarfiles(
        str(test_dataset_id),
        raw_files_path,
        dst_folder_fixture,
        target_size=target_size_in_bytes,
    )

    for info in tar_infos:
        assert info.unpackedSize >= single_file_size_in_bytes
        assert info.unpackedSize <= num_raw_files / expected_num_compressed_files * single_file_size_in_bytes
        assert info.packedSize >= single_file_size_in_bytes
        assert info.packedSize <= target_size_in_bytes * 1.05  # a tarfile might be "a little" larger than

    archive_files = [os.path.join(dst_folder_fixture, t) for t in dst_folder_fixture.iterdir()]
    assert expected_num_compressed_files == len(archive_files)
    assert len(tar_infos) == len(archive_files)

    verify_tar_content(raw_files_path, dst_folder_fixture, archive_files)


def verify_tar_content(raw_file_folder, datablock_folder, tars):
    expected_files = set()
    [expected_files.add(i) for i in datablock_operations.get_all_files_relative(raw_file_folder)]

    num_expected_files = len(expected_files)

    num_packed_files = 0
    for t in tars:
        tar: tarfile.TarFile = tarfile.open(Path(datablock_folder) / t)
        for f in tar.getnames():
            num_packed_files = num_packed_files + 1
            expected_files.discard(Path(f))

    assert num_packed_files == num_expected_files
    assert len(expected_files) == 0


@pytest.fixture()
def tar_infos_fixture(storage_paths_fixture) -> List[ArchiveInfo]:
    folder = create_raw_files_fixture(storage_paths_fixture, 10, 1 * MB)
    files = datablock_operations.get_all_files_relative(folder)

    tar_folder = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)
    tar_folder.mkdir(parents=True)

    assert len(files) > 2

    tar_infos = [
        ArchiveInfo(unpackedSize=0, packedSize=0, path=Path(""), fileCount=2),
        ArchiveInfo(unpackedSize=0, packedSize=0, path=Path(""), fileCount=2),
    ]

    tar1_path = tar_folder / "tar1.tar.gz"

    tar_infos[0].path = tar1_path

    if not tar1_path.exists():
        tar1 = tarfile.open(tar1_path, "w")
        for relative_path in files[:2]:
            full_path = Path(folder) / relative_path

            tar_infos[0].unpackedSize += full_path.stat().st_size
            tar1.add(name=full_path, arcname=relative_path, recursive=False)

        tar1.close()

        tar_infos[0].packedSize = tar1_path.stat().st_size

    tar2_path = tar_folder / "tar2.tar.gz"
    tar_infos[1].path = tar2_path

    if not tar2_path.exists():
        tar2 = tarfile.open(tar2_path, "w")
        for relative_path in files[2:]:
            full_path = Path(folder) / relative_path
            tar_infos[1].unpackedSize += full_path.stat().st_size
            tar2.add(name=full_path, arcname=relative_path, recursive=False)
        tar2.close()

        tar_infos[1].packedSize = tar2_path.stat().st_size

    return tar_infos


@pytest.fixture()
def origDataBlocks_fixture(storage_paths_fixture) -> List[OrigDataBlock]:
    import uuid

    folder = create_raw_files_fixture(storage_paths_fixture, 10, 1 * MB)

    blocks: List[OrigDataBlock] = []
    for f in folder.iterdir():
        p = folder / f
        blocks.append(
            OrigDataBlock(
                id=str(uuid.uuid4()),
                size=p.stat().st_size,
                ownerGroup=str(123),
                dataFileList=[DataFile(path=str(f), size=p.stat().st_size)],
            )
        )
    return blocks


@pytest.fixture()
def datablock_fixture(tar_infos_fixture) -> List[DataBlock]:
    target_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id=test_dataset_id)

    version = 1.0

    datablocks: List[DataBlock] = []
    for tar in tar_infos_fixture:
        data_file_list: List[DataFile] = []

        tar_path = target_folder / tar.path.name
        assert tar_path.exists()

        tarball = tarfile.open(tar_path, "r")

        for tar_info in tarball.getmembers():
            checksum = datablock_operations.calculate_md5_checksum(
                StoragePaths.scratch_archival_raw_files_folder(test_dataset_id) / tar_info.path
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
                archiveId=str(StoragePaths.relative_datablocks_folder(test_dataset_id) / tar_path.name),
                size=tar.unpackedSize,
                packedSize=tar.packedSize,
                chkAlg="md5",
                version=str(version),
                dataFileList=data_file_list,
            )
        )
        tarball.close()
        assert tar_path.exists()

    return datablocks


@pytest.fixture()
def storage_paths_fixture():
    lts_root = tempfile.TemporaryDirectory()
    scratch_root = tempfile.TemporaryDirectory()

    envs = {
        "LTS_STORAGE_ROOT": lts_root.name,
        "ARCHIVER_SCRATCH_FOLDER": scratch_root.name,
    }

    for k, v in envs.items():
        os.environ[k] = v

    yield

    for k, v in envs.items():
        os.environ.pop(k)

    # teardown
    import shutil

    lts_root = Path(lts_root.name)
    if lts_root.exists():
        shutil.rmtree(lts_root)

    scratch_root = Path(scratch_root.name)
    if scratch_root.exists():
        shutil.rmtree(scratch_root)


def create_datablock_in_lts(dataset_id: str):
    StoragePaths.lts_datablocks_folder(dataset_id).mkdir(parents=True, exist_ok=True)
    file_size_in_bytes = 1024 * 10
    file_in_lts = tempfile.NamedTemporaryFile(
        dir=StoragePaths.lts_datablocks_folder(dataset_id), delete=False
    )
    with open(file_in_lts.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))

    return file_in_lts


def create_raw_files_in_scratch(dataset: str):
    StoragePaths.scratch_archival_raw_files_folder(dataset).mkdir(parents=True, exist_ok=True)
    file = tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_raw_files_folder(dataset), delete=False
    )
    file_size_in_bytes = 1024 * 10
    with open(file.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file


def create_datablock_in_scratch(dataset: str):
    StoragePaths.scratch_archival_datablocks_folder(dataset).mkdir(parents=True, exist_ok=True)
    file = tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_datablocks_folder(dataset), delete=False
    )
    file_size_in_bytes = 1024 * 10
    with open(file.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file


def create_files_in_scratch(dataset: str):
    files = []
    StoragePaths.scratch_archival_datablocks_folder(dataset).mkdir(parents=True, exist_ok=True)
    files.append(
        tempfile.NamedTemporaryFile(
            dir=StoragePaths.scratch_archival_datablocks_folder(dataset), delete=False
        )
    )

    StoragePaths.scratch_archival_raw_files_folder(dataset).mkdir(parents=True, exist_ok=True)
    files.append(
        tempfile.NamedTemporaryFile(dir=StoragePaths.scratch_archival_raw_files_folder(dataset), delete=False)
    )

    for f in files:
        file_size_in_bytes = 1024 * 10
        with open(f.name, "wb") as f:
            f.write(os.urandom(file_size_in_bytes))

    return files


def test_create_datablock_entries(
    storage_paths_fixture,
    tar_infos_fixture: List[ArchiveInfo],
    origDataBlocks_fixture: List[OrigDataBlock],
):
    folder = create_raw_files_fixture(storage_paths_fixture, 10, 1 * MB)
    datablocks: List[DataBlock] = datablock_operations.create_datablock_entries(
        test_dataset_id,
        folder,
        origDataBlocks_fixture,
        tar_infos_fixture,
    )

    assert len(datablocks) == 2

    for datablock in datablocks:
        assert datablock.chkAlg == "md5"
        for datafile in datablock.dataFileList or []:
            expected_checksum = datablock_operations.calculate_md5_checksum(folder / datafile.path)
            assert expected_checksum == datafile.chk


def test_copy_file():
    file = tempfile.NamedTemporaryFile()
    name = file.name
    fileSizeInBytes = 1024 * 20
    with open(name, "wb") as f:
        f.write(os.urandom(fileSizeInBytes))

    with tempfile.TemporaryDirectory() as dst_folder:
        datablock_operations.copy_file_to_folder(Path(name).absolute(), Path(dst_folder))

        assert (Path(dst_folder) / Path(name).name).exists()


def test_verify_datablock_content(datablock_fixture):
    datablock_folder = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)

    # same checksum
    for d in datablock_fixture:
        datablock_operations.verify_datablock_content(
            datablock=d, datablock_path=datablock_folder / Path(d.archiveId).name
        )

    # different checksum
    with pytest.raises(SystemError):
        wrong_checksum_datablock = datablock_fixture[0]
        wrong_checksum_datablock.dataFileList[0].chk = "wrongChecksum"
        datablock_operations.verify_datablock_content(
            datablock=wrong_checksum_datablock,
            datablock_path=datablock_folder / wrong_checksum_datablock.archiveId,
        )

    # datablock does not exist
    with pytest.raises(SystemError):
        wrong_archive_id_datablock = datablock_fixture[0]
        wrong_archive_id_datablock.archiveId = "DatablockDoesNotExist.tar.gz"
        datablock_operations.verify_datablock_content(
            datablock=wrong_archive_id_datablock,
            datablock_path=datablock_folder / wrong_archive_id_datablock.archiveId,
        )

    # datafile does not exist
    with pytest.raises(SystemError):
        wrong_datafile_datablock = datablock_fixture[0]
        wrong_datafile_datablock.dataFileList[0].path = "DataFileDoesNotExist.img"
        datablock_operations.verify_datablock_content(
            datablock=wrong_datafile_datablock,
            datablock_path=datablock_folder / wrong_datafile_datablock.archiveId,
        )


def test_cleanup_lts(storage_paths_fixture):
    dataset = "1"
    file_in_lts = create_datablock_in_lts(dataset)

    assert Path(file_in_lts.name).exists()

    datablock_operations.cleanup_lts_folder(dataset_id=dataset)

    assert not Path(file_in_lts.name).exists()


def test_cleanup_scratch(storage_paths_fixture):
    dataset = "1"
    files_in_scratch = create_files_in_scratch(dataset)

    assert all([Path(f.name).exists() for f in files_in_scratch])

    datablock_operations.cleanup_scratch(dataset_id=dataset)

    assert all([not Path(f.name).exists() for f in files_in_scratch])


def mock_find_object_in_s3(*args, **kwargs):
    return True


def mock_download_objects_from_s3(*args, **kwargs):
    return [True]


@patch("archiver.utils.datablocks.find_object_in_s3", mock_find_object_in_s3)
@patch("archiver.utils.datablocks.download_object_from_s3", mock_download_objects_from_s3)
def test_move_data_to_LTS(storage_paths_fixture, datablock_fixture):
    for datablock in datablock_fixture:
        datablock_operations.move_data_to_LTS(test_dataset_id, datablock)

        file_in_lts = StoragePaths.lts_datablocks_folder(test_dataset_id) / Path(datablock.archiveId).name

        assert file_in_lts.exists()

        assert datablock_operations.calculate_md5_checksum(
            file_in_lts
        ) == datablock_operations.calculate_md5_checksum(file_in_lts)


def mock_list_s3_objects(*args, **kwargs):
    return [True]


def mock_upload_objects_to_s3(*args, **kwargs):
    pass


def mock_verify_objects(*args, **kwargs):
    return []


@patch("archiver.flows.retrieve_datasets_flow.get_s3_client", mock_s3client)
@patch("archiver.utils.datablocks.list_datablocks", mock_list_s3_objects)
@patch("archiver.utils.datablocks.download_objects_from_s3", mock_download_objects_from_s3)
@patch("archiver.utils.datablocks.upload_objects_to_s3", mock_upload_objects_to_s3)
@patch("archiver.utils.datablocks.verify_objects", mock_verify_objects)
def test_create_datablocks(
    storage_paths_fixture,
    origDataBlocks_fixture: List[OrigDataBlock],
):
    dataset_id = "testprefix/11.111"
    folder = create_raw_files_fixture(storage_paths_fixture, 10, 10 * MB)

    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True)
    raw_files_scratch_folder = StoragePaths.scratch_archival_raw_files_folder(dataset_id)

    for dir, _, raw_file in os.walk(folder):
        for file in raw_file:
            full_path = Path(dir) / file
            relative_folder = Path(dir).relative_to(folder)
            raw_files_scratch_folder.joinpath(relative_folder).mkdir(
                parents=True, exist_ok=True
            )

            shutil.copy(
                full_path,
                raw_files_scratch_folder
                .joinpath(relative_folder)
                .joinpath(file),
            )

    tar_files = datablock_operations.create_tarfiles(
        dataset_id=dataset_id,
        src_folder=raw_files_scratch_folder,
        dst_folder=datablocks_scratch_folder,
        target_size=500 * 1024 * 1024
    )

    datablocks = datablock_operations.create_datablock_entries(
        dataset_id=dataset_id,
        folder=datablocks_scratch_folder,
        origDataBlocks=origDataBlocks_fixture,
        tar_infos=tar_files
    )

    assert len(datablocks) == 1

    assert all([(StoragePaths.scratch_archival_root() / d.archiveId).exists() for d in datablocks])

    created_tars = [(StoragePaths.scratch_archival_root() / d.archiveId) for d in datablocks]

    verify_tar_content(
        folder,
        StoragePaths.scratch_archival_datablocks_folder(dataset_id),
        created_tars,
    )
