import pytest
import os
import tarfile
from typing import List
from pathlib import Path
import tempfile
from unittest.mock import patch

from archiver.utils.datablocks import create_tarballs, create_datablock_entries
import archiver.utils.datablocks as datablock_operations
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile
from archiver.flows.utils import StoragePaths, SystemError


test_id = 1234
num_files = 10
file_size_in_bytes = 1024 * 1024
target_size = 2 * file_size_in_bytes - 1
expected_num_files = 5


@pytest.fixture(scope="session")
def temp_folder(tmp_path_factory: pytest.TempPathFactory):
    folder: Path = tmp_path_factory.mktemp(str(test_id))
    for n in range(num_files):
        filename = folder / f"img_{n}.png"
        with open(filename, 'wb') as fout:
            print(f"Creating file {filename}")
            fout.write(os.urandom(file_size_in_bytes))
    return folder


def test_create_tarballs(temp_folder: Path):
    tarballs = create_tarballs(
        test_id, temp_folder, target_size=target_size)

    tars = [t for t in temp_folder.iterdir() if t.suffix == ".gz"]
    assert len(tars) == expected_num_files

    assert tarballs.sort() == tars.sort()

    expected_files = set([temp_folder / t for t in temp_folder.iterdir() if not t.suffix == ".gz"])

    for t in tars:
        tar: tarfile.TarFile = tarfile.open(os.path.join(temp_folder, t))
        for f in tar.getnames():
            expected_files.discard("/" / Path(f))

    assert len(expected_files) == 0


@ pytest.fixture()
def tarfiles(temp_folder: Path):

    files = list(temp_folder.iterdir())

    assert len(files) > 2

    tar1_path = os.path.join(temp_folder, "tar1.tar.gz")

    tar1 = tarfile.open(tar1_path, 'x:gz', compresslevel=6)
    for f in files[:2]:
        tar1.add(temp_folder / f)
    tar1.close()

    tar2_path = os.path.join(temp_folder, "tar2.tar.gz")
    tar2 = tarfile.open(tar2_path, 'x:gz', compresslevel=6)
    for f in files[2:]:
        tar2.add(temp_folder / f)
    tar2.close()

    return [tar1_path, tar2_path]


@ pytest.fixture()
def origDataBlocks(temp_folder: Path) -> List[OrigDataBlock]:
    import uuid
    blocks: List[OrigDataBlock] = []
    for f in temp_folder.iterdir():
        p = temp_folder / f
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


@pytest.fixture()
def datablock() -> DataBlock:
    import uuid
    return DataBlock(
        id=str(uuid.uuid4()),
        archiveId=str(Path(StoragePaths.relative_datablocks_folder(1)) / "test_file.tar.gz"),
        size=1,
        packedSize=1,
        chkAlg="md5",
        version=str(1),
        ownerGroup=str(1)
        # accessGroups=o.accessGroups,
        # instrumentGroup=o.instrumentGroup,
        # # createdBy=
        # # updatedBy=
        # # updatedAt=datetime.datetime.isoformat(),
        # datasetId=str(dataset_id),
        # dataFileList=data_file_list,
        # rawDatasetId=o.rawdatasetId,
        # derivedDatasetId=o.derivedDatasetId
    )


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


def create_file_in_lts(dataset: int):
    StoragePaths.lts_datablocks_folder(dataset).mkdir(parents=True, exist_ok=True)
    file_size_in_bytes = 1024 * 10
    file_in_lts = tempfile.NamedTemporaryFile(dir=StoragePaths.lts_datablocks_folder(dataset), delete=False)
    with open(file_in_lts.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file_in_lts


def create_file_in_scratch(dataset: int):
    StoragePaths.scratch_datablocks_folder(dataset).mkdir(parents=True, exist_ok=True)
    file_size_in_bytes = 1024 * 10
    file_in_scratch = tempfile.NamedTemporaryFile(dir=StoragePaths.scratch_datablocks_folder(dataset), delete=False)
    with open(file_in_scratch.name, "wb") as f:
        f.write(os.urandom(file_size_in_bytes))
    return file_in_scratch


def test_create_datablock_entries(temp_folder: Path, tarfiles: List[Path], origDataBlocks: List[OrigDataBlock]):

    datablocks: List[DataBlock] = create_datablock_entries(test_id, temp_folder, origDataBlocks, tarfiles)

    assert len(datablocks) == 2


def test_copy_file():

    file = tempfile.NamedTemporaryFile()
    name = file.name
    fileSizeInBytes = 1024 * 20
    with open(name, "wb") as f:
        f.write(os.urandom(fileSizeInBytes))

    with tempfile.TemporaryDirectory() as dst_folder:
        datablock_operations.copy_file_to_folder(Path(name).absolute(), Path(dst_folder))

        assert (Path(dst_folder) / Path(name).name).exists()


def test_verify_data_in_LTS(storage_paths_fixture, datablock):

    # create file in fake LTS
    dataset = 1
    file_in_lts = create_file_in_lts(dataset)

    expected_checksum = datablock_operations.calculate_checksum(Path(file_in_lts.name))

    datablock.archiveId = file_in_lts.name

    # same checksum
    datablock_operations.verify_data_in_LTS(dataset, datablock, expected_checksum)

    # different checksum
    with pytest.raises(SystemError):
        datablock_operations.verify_data_in_LTS(dataset, datablock, "asdf")

    # file does not exist
    with pytest.raises(SystemError):
        datablock.archiveId = "FileDoesNotExist.tar.gz"
        datablock_operations.verify_data_in_LTS(dataset, datablock, expected_checksum)


def test_cleanup_lts(storage_paths_fixture):
    dataset = 1
    file_in_lts = create_file_in_lts(dataset)

    assert Path(file_in_lts.name).exists()

    datablock_operations.cleanup_lts_folder(dataset_id=dataset)

    assert not Path(file_in_lts.name).exists()


def test_cleanup_scratch(storage_paths_fixture):
    dataset = 1
    file_in_lts = create_file_in_scratch(dataset)

    assert Path(file_in_lts.name).exists()

    datablock_operations.cleanup_scratch(dataset_id=dataset)

    assert not Path(file_in_lts.name).exists()


def mock_find_object_in_s3(*args, **kwargs):
    return True


def mock_download_objects_from_s3(*args, **kwargs):
    return [True]


@ patch("archiver.utils.datablocks.find_object_in_s3", mock_find_object_in_s3)
@ patch("archiver.utils.datablocks.download_object_from_s3", mock_download_objects_from_s3)
def test_move_data_to_LTS(storage_paths_fixture, datablock):

    dataset_id = 1
    file = create_file_in_scratch(dataset_id)
    expected_checksum = datablock_operations.calculate_checksum(Path(file.name))

    datablock.archiveId = file.name
    checksum = datablock_operations.move_data_to_LTS(dataset_id, datablock)

    assert expected_checksum == checksum

    file_in_lts = StoragePaths.lts_datablocks_folder(dataset_id) / datablock.archiveId

    assert file_in_lts.exists()

    assert expected_checksum == datablock_operations.calculate_checksum(file_in_lts)


def mock_list_s3_objects(*args, **kwargs):
    return [True]


def mock_upload_objects_to_s3(*args, **kwargs):
    pass


def mock_verify_objects(*args, **kwargs):
    return []


@ patch("archiver.utils.datablocks.list_s3_objects", mock_list_s3_objects)
@ patch("archiver.utils.datablocks.download_objects_from_s3", mock_download_objects_from_s3)
@ patch("archiver.utils.datablocks.upload_objects_to_s3", mock_upload_objects_to_s3)
@ patch("archiver.utils.datablocks.verify_objects", mock_verify_objects)
def test_create_datablocks(temp_folder, storage_paths_fixture, origDataBlocks: List[OrigDataBlock]):
    dataset_id = 1

    import shutil
    scratch = StoragePaths.scratch_folder(dataset_id)
    shutil.copytree(temp_folder.absolute(), scratch)

    # Act
    datablocks = datablock_operations.create_datablocks(dataset_id=dataset_id, origDataBlocks=origDataBlocks)

    assert len(datablocks) == 1

    for d in datablocks:
        assert (StoragePaths.scratch_root() / d.archiveId).exists()
