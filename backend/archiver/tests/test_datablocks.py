import pytest
import os
import tarfile
from typing import List
from pathlib import Path

from archiver.utils.datablocks import create_tarballs, create_datablock_entries
from archiver.utils.model import OrigDataBlock, DataBlock, DataFile

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


def test_create_datablock_entries(temp_folder: Path, tarfiles: List[Path], origDataBlocks: List[OrigDataBlock]):

    datablocks: List[DataBlock] = create_datablock_entries(test_id, temp_folder, origDataBlocks, tarfiles)

    assert len(datablocks) == 2
