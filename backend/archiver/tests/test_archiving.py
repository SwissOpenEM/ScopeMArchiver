import pytest
import os
import tarfile

from archiver.datablocks import create_tarballs

test_id = 1234
num_files = 10
file_size_in_bytes = 1024 * 1024
target_size = 2 * file_size_in_bytes - 1
expected_num_files = 5


@pytest.fixture(scope="session")
def test_folder(tmpdir_factory):
    folder = tmpdir_factory.mktemp(str(test_id))
    for n in range(num_files):
        filename = folder.join(f"img_{n}.png")
        with open(filename, 'wb') as fout:
            print(f"Creating file {filename}")
            fout.write(os.urandom(file_size_in_bytes))
    return folder


def test_create_tarballs(test_folder):
    tarballs = create_tarballs(
        test_id, test_folder, target_size=target_size)

    tars = [t for t in os.listdir(test_folder) if t.endswith(".tar.gz")]
    assert len(tars) == expected_num_files

    assert tarballs.sort() == tars.sort()

    expected_files = set([os.path.join(test_folder, t)
                          for t in os.listdir(test_folder)
                          if not t.endswith(".tar.gz")])

    for t in tars:
        tar = tarfile.open(os.path.join(test_folder, t))
        for f in tar.getnames():
            expected_files.discard("/" + f)

    assert len(expected_files) == 0
