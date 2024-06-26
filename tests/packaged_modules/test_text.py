import textwrap

import pyarrow as pa
import pytest

from datasets import Features, Image
from datasets.builder import InvalidConfigName
from datasets.data_files import DataFilesList
from datasets.packaged_modules.text.text import Text, TextConfig

from ..utils import require_pil


@pytest.fixture
def text_file(tmp_path):
    filename = tmp_path / "text.txt"
    data = textwrap.dedent(
        """\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
        Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
        Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.

        Second paragraph:
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
        Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
        Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
        """
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(data)
    return str(filename)


@pytest.fixture
def text_file_with_image(tmp_path, image_file):
    filename = tmp_path / "text_with_image.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(image_file)
    return str(filename)


def test_config_raises_when_invalid_name() -> None:
    with pytest.raises(InvalidConfigName, match="Bad characters"):
        _ = TextConfig(name="name-with-*-invalid-character")


@pytest.mark.parametrize("data_files", ["str_path", ["str_path"], DataFilesList(["str_path"], [()])])
def test_config_raises_when_invalid_data_files(data_files) -> None:
    with pytest.raises(ValueError, match="Expected a DataFilesDict"):
        _ = TextConfig(name="name", data_files=data_files)


@pytest.mark.parametrize("keep_linebreaks", [True, False])
def test_text_linebreaks(text_file, keep_linebreaks):
    with open(text_file, encoding="utf-8") as f:
        expected_content = f.read().splitlines(keepends=keep_linebreaks)
    text = Text(keep_linebreaks=keep_linebreaks, encoding="utf-8")
    generator = text._generate_tables([[text_file]])
    generated_content = pa.concat_tables([table for _, table in generator]).to_pydict()["text"]
    assert generated_content == expected_content


@require_pil
def test_text_cast_image(text_file_with_image):
    with open(text_file_with_image, encoding="utf-8") as f:
        image_file = f.read().splitlines()[0]
    text = Text(encoding="utf-8", features=Features({"image": Image()}))
    generator = text._generate_tables([[text_file_with_image]])
    pa_table = pa.concat_tables([table for _, table in generator])
    assert pa_table.schema.field("image").type == Image()()
    generated_content = pa_table.to_pydict()["image"]
    assert generated_content == [{"path": image_file, "bytes": None}]


@pytest.mark.parametrize("sample_by", ["line", "paragraph", "document"])
def test_text_sample_by(sample_by, text_file):
    with open(text_file, encoding="utf-8") as f:
        expected_content = f.read()
    if sample_by == "line":
        expected_content = expected_content.splitlines()
    elif sample_by == "paragraph":
        expected_content = expected_content.split("\n\n")
    elif sample_by == "document":
        expected_content = [expected_content]
    text = Text(sample_by=sample_by, encoding="utf-8", chunksize=100)
    generator = text._generate_tables([[text_file]])
    generated_content = pa.concat_tables([table for _, table in generator]).to_pydict()["text"]
    assert generated_content == expected_content
