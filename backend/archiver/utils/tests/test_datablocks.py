import datetime
import shutil
import pytest
import os
import tarfile
from typing import Dict, List
from pathlib import Path
import tempfile
from unittest.mock import patch

from archiver.flows.tests.helpers import mock_s3client
from archiver.utils.datablocks import TarInfo
import archiver.utils.datablocks as datablock_operations
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.flows.utils import StoragePaths, SystemError


test_dataset_id = "testprefix/1234.4567"
num_raw_files = 10
file_size_in_bytes = 1024 * 1024

expected_num_compressed_files = 5


@pytest.fixture()
def create_raw_files_fixture(storage_paths_fixture):
    folder: Path = StoragePaths.scratch_archival_raw_files_folder(test_dataset_id)
    folder.mkdir(parents=True)
    for n in range(num_raw_files):
        filename = folder / f"img_{n}.png"
        with open(filename, 'wb') as fout:
            print(f"Creating file {filename}")
            fout.write(os.urandom(file_size_in_bytes))
    return folder


@pytest.fixture()
def dst_folder_fixtrue(storage_paths_fixture):
    folder: Path = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)
    folder.mkdir(parents=True)
    return folder


def test_create_tarballs(create_raw_files_fixture: Path, dst_folder_fixtrue: Path):

    target_size = int(2.5 * file_size_in_bytes)

    tar_infos = datablock_operations.create_tarballs(
        str(test_dataset_id), create_raw_files_fixture, dst_folder_fixtrue, target_size=target_size)

    tars = [t for t in dst_folder_fixtrue.iterdir()]
    assert len(tars) == expected_num_compressed_files
    assert len(tar_infos) == len(tars)

    verify_tar_content(create_raw_files_fixture, dst_folder_fixtrue, tars)


def verify_tar_content(raw_file_folder, datablock_folder, tars):
    expected_files = set(
        [t.name for t in raw_file_folder.iterdir()])

    num_expected_files = len(expected_files)

    num_packed_files = 0
    for t in tars:
        tar: tarfile.TarFile = tarfile.open(Path(datablock_folder) / t)
        for f in tar.getnames():
            num_packed_files = num_packed_files + 1
            expected_files.discard(f)

    assert num_packed_files == num_expected_files
    assert len(expected_files) == 0


@ pytest.fixture()
def tar_infos_fixture(create_raw_files_fixture: Path) -> List[TarInfo]:

    files = list(create_raw_files_fixture.iterdir())

    tar_folder = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)
    tar_folder.mkdir(parents=True)

    assert len(files) > 2

    tar_infos = [
        TarInfo(
            unpackedSize=0,
            packedSize=0,
            path=Path("")),
        TarInfo(
            unpackedSize=0,
            packedSize=0,
            path=Path(""))
    ]

    tar1_path = tar_folder / "tar1.tar.gz"

    tar_infos[0].path = tar1_path

    if not tar1_path.exists():
        tar1 = tarfile.open(tar1_path, 'w')
        for f in files[:2]:
            p = Path(create_raw_files_fixture) / f

            tar_infos[0].unpackedSize += p.stat().st_size
            tar1.add(name=p,
                     arcname=f.name, recursive=False)

        tar1.close()

        tar_infos[0].packedSize = tar1_path.stat().st_size

    tar2_path = tar_folder / "tar2.tar.gz"
    tar_infos[1].path = tar2_path

    if not tar2_path.exists():
        tar2 = tarfile.open(tar2_path, 'w')
        for f in files[2:]:
            p = Path(create_raw_files_fixture) / f
            tar_infos[1].unpackedSize += p.stat().st_size
            tar2.add(name=p,
                     arcname=f.name, recursive=False)
        tar2.close()

        tar_infos[1].packedSize = tar2_path.stat().st_size

    return tar_infos


@ pytest.fixture()
def origDataBlocks_fixture(create_raw_files_fixture: Path) -> List[OrigDataBlock]:
    import uuid
    blocks: List[OrigDataBlock] = []
    for f in create_raw_files_fixture.iterdir():
        p = create_raw_files_fixture / f
        blocks.append(
            OrigDataBlock(id=str(uuid.uuid4()),
                          size=p.stat().st_size,
                          ownerGroup=str(123),
                          dataFileList=[DataFile(
                              path=str(f),
                              size=p.stat().st_size
                          )]
                          )
        )
    return blocks


@ pytest.fixture()
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
            checksum = datablock_operations.calculate_md5_checksum(StoragePaths.scratch_archival_raw_files_folder(
                test_dataset_id) / tar_info.path)

            data_file_list.append(DataFile(
                path=tar_info.path,
                size=tar_info.size,
                chk=checksum,
                uid=str(tar_info.uid),
                gid=str(tar_info.gid),
                perm=str(tar_info.mode),
                time=str(datetime.datetime.now(datetime.UTC).isoformat())
            ))

        datablocks.append(DataBlock(
            archiveId=str(StoragePaths.relative_datablocks_folder(
                test_dataset_id) / tar_path.name),
            size=tar.unpackedSize,
            packedSize=tar.packedSize,
            chkAlg="md5",
            version=str(version),
            dataFileList=data_file_list,
        ))
        tarball.close()
        assert tar_path.exists()

    return datablocks


@ pytest.fixture()
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

    StoragePaths.lts_datablocks_folder(
        dataset_id).mkdir(parents=True, exist_ok=True)
    file_size_in_bytes = 1024 * 10
    file_in_lts = tempfile.NamedTemporaryFile(
        dir=StoragePaths.lts_datablocks_folder(dataset_id), delete=False)
    with open(file_in_lts.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))

    return file_in_lts


def create_raw_files_in_scratch(dataset: str):
    StoragePaths.scratch_archival_raw_files_folder(
        dataset).mkdir(parents=True, exist_ok=True)
    file = tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_raw_files_folder(dataset), delete=False)
    file_size_in_bytes = 1024 * 10
    with open(file.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file


def create_datablock_in_scratch(dataset: str):
    StoragePaths.scratch_archival_datablocks_folder(
        dataset).mkdir(parents=True, exist_ok=True)
    file = tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_datablocks_folder(dataset), delete=False)
    file_size_in_bytes = 1024 * 10
    with open(file.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file


def create_files_in_scratch(dataset: str):
    files = []
    StoragePaths.scratch_archival_datablocks_folder(
        dataset).mkdir(parents=True, exist_ok=True)
    files.append(tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_datablocks_folder(dataset), delete=False))

    StoragePaths.scratch_archival_raw_files_folder(
        dataset).mkdir(parents=True, exist_ok=True)
    files.append(tempfile.NamedTemporaryFile(
        dir=StoragePaths.scratch_archival_raw_files_folder(dataset), delete=False))

    for f in files:
        file_size_in_bytes = 1024 * 10
        with open(f.name, "wb") as f:
            f.write(os.urandom(file_size_in_bytes))

    return files


def test_create_datablock_entries(
    storage_paths_fixture,
        create_raw_files_fixture: Path, tar_infos_fixture: List[TarInfo],
        origDataBlocks_fixture: List[OrigDataBlock]):

    datablocks: List[DataBlock] = datablock_operations.create_datablock_entries(
        test_dataset_id, create_raw_files_fixture, origDataBlocks_fixture, tar_infos_fixture)

    assert len(datablocks) == 2

    for datablock in datablocks:
        assert datablock.chkAlg == "md5"
        for datafile in datablock.dataFileList or []:
            expected_checksum = datablock_operations.calculate_md5_checksum(create_raw_files_fixture / datafile.path)
            assert expected_checksum == datafile.chk


def test_copy_file():

    file = tempfile.NamedTemporaryFile()
    name = file.name
    fileSizeInBytes = 1024 * 20
    with open(name, "wb") as f:
        f.write(os.urandom(fileSizeInBytes))

    with tempfile.TemporaryDirectory() as dst_folder:
        datablock_operations.copy_file_to_folder(
            Path(name).absolute(), Path(dst_folder))

        assert (Path(dst_folder) / Path(name).name).exists()


def test_verify_datablock(datablock_fixture):

    datablock_folder = StoragePaths.scratch_archival_datablocks_folder(test_dataset_id)

    # same checksum
    for d in datablock_fixture:
        datablock_operations.verify_datablock(datablock=d, datablock_path=datablock_folder / Path(d.archiveId).name)

    # different checksum
    with pytest.raises(SystemError):
        wrong_checksum_datablock = datablock_fixture[0]
        wrong_checksum_datablock.dataFileList[0].chk = "wrongChecksum"
        datablock_operations.verify_datablock(datablock=wrong_checksum_datablock,
                                              datablock_path=datablock_folder / wrong_checksum_datablock.archiveId)

    # datablock does not exist
    with pytest.raises(SystemError):
        wrong_archive_id_datablock = datablock_fixture[0]
        wrong_archive_id_datablock.archiveId = "DatablockDoesNotExist.tar.gz"
        datablock_operations.verify_datablock(datablock=wrong_archive_id_datablock,
                                              datablock_path=datablock_folder / wrong_archive_id_datablock.archiveId)

    # datafile does not exist
    with pytest.raises(SystemError):
        wrong_datafile_datablock = datablock_fixture[0]
        wrong_datafile_datablock.dataFileList[0].path = "DataFileDoesNotExist.img"
        datablock_operations.verify_datablock(datablock=wrong_datafile_datablock,
                                              datablock_path=datablock_folder / wrong_datafile_datablock.archiveId)


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


@ patch("archiver.utils.datablocks.find_object_in_s3", mock_find_object_in_s3)
@ patch("archiver.utils.datablocks.download_object_from_s3", mock_download_objects_from_s3)
def test_move_data_to_LTS(storage_paths_fixture, datablock_fixture):

    for datablock in datablock_fixture:
        datablock_operations.move_data_to_LTS(mock_s3client(), test_dataset_id, datablock)

        file_in_lts = StoragePaths.lts_datablocks_folder(
            test_dataset_id) / Path(datablock.archiveId).name

        assert file_in_lts.exists()

        assert datablock_operations.calculate_md5_checksum(file_in_lts) == datablock_operations.calculate_md5_checksum(
            file_in_lts)


def mock_list_s3_objects(*args, **kwargs):
    return [True]


def mock_upload_objects_to_s3(*args, **kwargs):
    pass


def mock_verify_objects(*args, **kwargs):
    return []


@patch("archiver.flows.retrieve_datasets_flow.get_s3_client", mock_s3client)
@ patch("archiver.utils.datablocks.list_datablocks", mock_list_s3_objects)
@ patch("archiver.utils.datablocks.download_objects_from_s3", mock_download_objects_from_s3)
@ patch("archiver.utils.datablocks.upload_objects_to_s3", mock_upload_objects_to_s3)
@ patch("archiver.utils.datablocks.verify_objects", mock_verify_objects)
def test_create_datablocks(create_raw_files_fixture, storage_paths_fixture, origDataBlocks_fixture: List[OrigDataBlock]):
    dataset_id = "testprefix/11.111"

    for raw_file in create_raw_files_fixture.iterdir():
        StoragePaths.scratch_archival_raw_files_folder(
            dataset_id).mkdir(parents=True, exist_ok=True)
        shutil.copy(raw_file, StoragePaths.scratch_archival_raw_files_folder(
            dataset_id) / Path(raw_file).name)

    # Act
    datablocks = datablock_operations.create_datablocks(mock_s3client(),
                                                        dataset_id=dataset_id, origDataBlocks=origDataBlocks_fixture)

    assert len(datablocks) == 1

    assert all([(StoragePaths.scratch_archival_root() /
               d.archiveId).exists() for d in datablocks])

    created_tars = [(StoragePaths.scratch_archival_root() / d.archiveId)
                    for d in datablocks]

    verify_tar_content(create_raw_files_fixture, StoragePaths.scratch_archival_datablocks_folder(
        dataset_id), created_tars)
