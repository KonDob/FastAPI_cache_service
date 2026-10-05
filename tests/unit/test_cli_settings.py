"""Command line parsing and sanitizing of cache-cli arguments."""

import io
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import CliApp

from cache_cli.settings import CliSettings, PayloadRequest

REQUEST_JSON = '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
REQUEST = PayloadRequest(list_1=["a", "b"], list_2=["c", "d"])


def parse(*args: str) -> CliSettings:
    return CliApp.run(CliSettings, cli_args=list(args))


def test_defaults() -> None:
    settings = parse("-j", REQUEST_JSON)

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.output_file == "-"


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["-H", "http://example.com:9000", "-r", "3", "-o", "out.json"], id="short"),
        pytest.param(
            ["--host", "http://example.com:9000", "--repeat", "3", "--output", "out.json"],
            id="long",
        ),
    ],
)
def test_short_and_long_flags_are_equivalent(args: list[str]) -> None:
    settings = parse(*args, "-j", REQUEST_JSON)

    assert str(settings.host) == "http://example.com:9000/"
    assert settings.repeat == 3
    assert settings.output_file == "out.json"


@pytest.mark.parametrize(
    ("args", "loc", "message"),
    [
        pytest.param([], (), "exactly one of --input or --json", id="no-input"),
        pytest.param(
            ["-i", "-", "-j", REQUEST_JSON],
            (),
            "exactly one of --input or --json",
            id="both-inputs",
        ),
        pytest.param(
            ["-r", "0", "-j", REQUEST_JSON], ("r",), "greater than or equal to 1", id="repeat-0"
        ),
        pytest.param(
            ["-H", "ftp://example.com", "-j", REQUEST_JSON], ("H",), "URL scheme", id="host-scheme"
        ),
        pytest.param(["-i", "missing.json"], ("i",), "file not found", id="input-missing"),
        pytest.param(
            ["-o", "no/such/dir/out.json", "-j", REQUEST_JSON],
            ("o",),
            "directory not found",
            id="output-directory-missing",
        ),
        pytest.param(["-j", "not json"], ("j",), "Invalid JSON", id="json-malformed"),
        pytest.param(
            ["-j", '{"list_1": ["a"]}'], ("j", "list_2"), "Field required", id="json-missing-list"
        ),
        pytest.param(
            ["-j", '{"list_1": ["a"], "list_2": []}'], ("j",), "same length", id="json-lengths"
        ),
    ],
)
def test_invalid_arguments_are_rejected(
    args: list[str], loc: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        parse(*args)

    errors = caught.value.errors()
    assert any(error["loc"] == loc and message in error["msg"] for error in errors), errors


def test_environment_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("host", "http://from-env:1")
    monkeypatch.setenv("repeat", "7")

    settings = parse("-j", REQUEST_JSON)

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1


def test_request_is_loaded_from_inline_json() -> None:
    assert parse("-j", REQUEST_JSON).load_request() == REQUEST


def test_request_is_loaded_from_file(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text(REQUEST_JSON, encoding="utf-8")

    assert parse("-i", str(path)).load_request() == REQUEST


def test_request_is_loaded_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(REQUEST_JSON))

    assert parse("-i", "-").load_request() == REQUEST


def test_invalid_request_in_file_is_rejected_on_load(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text('{"list_1": ["a"], "list_2": [1]}', encoding="utf-8")
    settings = parse("-i", str(path))

    with pytest.raises(ValidationError):
        settings.load_request()
