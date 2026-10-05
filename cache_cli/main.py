"""Entry point of the `cache-cli` command."""

import json
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx2
from pydantic import ValidationError
from pydantic_settings import CliApp

from cache_cli.client import IterationResult, ServiceError, run
from cache_cli.settings import STDIO, CliSettings

# Exit codes follow the usual convention: 2 for bad usage, 1 for a failed run.
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

_FLAGS = {"H": "--host", "r": "--repeat", "i": "--input", "j": "--json", "o": "--output"}


def main(argv: Sequence[str] | None = None, http_client: httpx2.Client | None = None) -> int:
    """Run the tool; `http_client` lets tests talk to the app without a real server."""
    try:
        settings = CliApp.run(CliSettings, cli_args=list(sys.argv[1:] if argv is None else argv))
        request = settings.load_request()
    except ValidationError as error:
        _print_error(_describe(error))
        return EXIT_USAGE
    except (OSError, UnicodeDecodeError) as error:
        _print_error(f"cannot read input: {error}")
        return EXIT_USAGE

    try:
        if http_client is None:
            with httpx2.Client(base_url=str(settings.host)) as client:
                results = run(client, request, settings.repeat)
        else:
            results = run(http_client, request, settings.repeat)
    except ServiceError as error:
        _print_error(str(error))
        return EXIT_FAILURE

    try:
        _write(results, settings.output_file)
    except OSError as error:
        _print_error(f"cannot write output: {error}")
        return EXIT_FAILURE
    return EXIT_OK


def _describe(error: ValidationError) -> str:
    lines = []
    for item in error.errors():
        message = item["msg"].removeprefix("Value error, ")
        loc = [str(part) for part in item["loc"]]
        # A leading alias names the command line option; the rest points into the request JSON.
        flag = _FLAGS.get(loc[0]) if loc else None
        path = ".".join(loc[1:] if flag else loc)
        where = " ".join(part for part in (flag, path) if part)
        lines.append(f"{where}: {message}" if where else message)
    return "\n".join(lines)


def _write(results: list[IterationResult], destination: str) -> None:
    text = json.dumps([result.model_dump() for result in results], indent=2, ensure_ascii=False)
    if destination == STDIO:
        print(text)
    else:
        Path(destination).write_text(text + "\n", encoding="utf-8")


def _print_error(message: str) -> None:
    print(f"cache-cli: error: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
