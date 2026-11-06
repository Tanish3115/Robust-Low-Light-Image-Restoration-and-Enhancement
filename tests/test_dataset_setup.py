from pathlib import Path
import zipfile

import pytest

from scripts.setup_dataset import prepare


def test_dataset_archive_rejects_path_traversal(tmp_path):
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as file:file.writestr('../outside.png',b'x')
    with pytest.raises(ValueError,match='Unsafe'):prepare(archive,tmp_path/'dataset')
    assert not (tmp_path/'outside.png').exists()


def test_incomplete_dataset_is_not_claimed_as_the_official_partition(tmp_path):
    archive=tmp_path/'incomplete.zip'
    with zipfile.ZipFile(archive,'w') as file:file.writestr('readme.txt','Missing the image partitions')
    with pytest.raises(ValueError,match='official partition'):prepare(archive,tmp_path/'dataset')
