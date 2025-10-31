import re
from scicat.scicat_tasks import sanitize_name


def is_valid_string(input_string):
    pattern = r'^[a-z0-9-]+$'  # Regex pattern
    return bool(re.match(pattern, input_string))  # Check for a match


def test_sanitize_name():

    dataset_id = "20.500.11935/71f11078-77bb-469d-90e6-dcb4a8fd7e93"

    sanatized = sanitize_name(dataset_id)

    assert is_valid_string(sanatized)
