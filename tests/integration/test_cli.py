"""cache-cli end to end: real argument parsing and HTTP calls into the app under test."""

import io
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.transformer import TransformerError, get_transformer
from cache_cli.main import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main
from tests.integration.fakes import CountingTransformer

REQUEST_JSON = '{"list_1": ["first", "second"], "list_2": ["other", "another"]}'
EXPECTED_OUTPUT = "FIRST, OTHER, SECOND, ANOTHER"


def _results(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = json.loads(text)
    return results


def test_repeat_sends_the_same_request_and_reuses_the_id(
    client: TestClient, transformer: CountingTransformer, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["-j", REQUEST_JSON, "-r", "3"], http_client=client)

    results = _results(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert [result["iteration"] for result in results] == [1, 2, 3]
    assert [result["status"] for result in results] == ["created", "existing", "existing"]
    assert len({result["id"] for result in results}) == 1
    assert {result["output"] for result in results} == {EXPECTED_OUTPUT}
    assert len(transformer.calls) == 1


def test_results_are_written_to_output_file(
    client: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "results.json"

    exit_code = main(["-j", REQUEST_JSON, "-o", str(output)], http_client=client)

    assert exit_code == EXIT_OK
    assert capsys.readouterr().out == ""
    assert _results(output.read_text(encoding="utf-8"))[0]["output"] == EXPECTED_OUTPUT


def test_request_is_read_from_stdin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(REQUEST_JSON))

    exit_code = main(["-i", "-"], http_client=client)

    assert exit_code == EXIT_OK
    assert _results(capsys.readouterr().out)[0]["output"] == EXPECTED_OUTPUT


def _unavailable(values: Sequence[str]) -> list[str]:
    raise TransformerError("connection refused")


def test_server_error_exits_with_failure(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app.dependency_overrides[get_transformer] = lambda: _unavailable

    exit_code = main(["-j", REQUEST_JSON], http_client=client)

    captured = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert captured.out == ""
    assert "POST /payload returned 502" in captured.err


def test_request_rejected_by_server_exits_with_failure(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    # Passes the CLI's own checks but breaks a server-side limit.
    body = json.dumps({"list_1": ["a" * 1001], "list_2": ["b"]})

    exit_code = main(["-j", body], http_client=client)

    assert exit_code == EXIT_FAILURE
    assert "POST /payload returned 422" in capsys.readouterr().err


def test_unexpected_response_exits_with_failure(capsys: pytest.CaptureFixture[str]) -> None:
    # --host pointing at some other web server that answers 200 with HTML.
    foreign = httpx2.Client(
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, text="<html></html>")),
        base_url="http://elsewhere",
    )

    exit_code = main(["-j", REQUEST_JSON], http_client=foreign)

    assert exit_code == EXIT_FAILURE
    assert "POST /payload returned an unexpected response" in capsys.readouterr().err


def test_unwritable_output_exits_with_failure(
    client: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Valid arguments (the parent directory exists), yet a directory cannot be written as a file.
    exit_code = main(["-j", REQUEST_JSON, "-o", str(tmp_path)], http_client=client)

    assert exit_code == EXIT_FAILURE
    assert "cannot write output" in capsys.readouterr().err


def test_unreachable_server_exits_with_failure(capsys: pytest.CaptureFixture[str]) -> None:
    # Port 9 (discard) has no listener on a normal machine, so the connection is refused.
    exit_code = main(["-H", "http://127.0.0.1:9", "-j", REQUEST_JSON])

    assert exit_code == EXIT_FAILURE
    assert "POST /payload failed" in capsys.readouterr().err


def test_invalid_arguments_exit_with_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["-r", "0", "-j", REQUEST_JSON])

    captured = capsys.readouterr()
    assert exit_code == EXIT_USAGE
    assert (
        captured.err == "cache-cli: error: --repeat: Input should be greater than or equal to 1\n"
    )
