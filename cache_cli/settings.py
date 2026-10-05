"""Command line arguments, parsed and sanitized by Pydantic Settings."""

import sys
from pathlib import Path
from typing import Literal, Self, TextIO

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

STDIO: Literal["-"] = "-"


class PayloadRequest(BaseModel):
    """Body of POST /payload, checked locally so obvious mistakes never reach the server."""

    list_1: list[str]
    list_2: list[str]

    @model_validator(mode="after")
    def lists_must_match_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class CliSettings(BaseSettings):
    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        cli_hide_none_type=True,
        # Without this the -H alias is lower-cased and clashes with -h/--help.
        case_sensitive=True,
    )

    host: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("H", "host"),
        description="Base URL of the caching service.",
    )
    repeat: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices("r", "repeat"),
        description="Number of times the same request is sent.",
    )
    # Plain strings rather than `"-" | FilePath`: a union reports errors for every branch,
    # which is unreadable on the command line.
    input_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("i", "input"),
        description='File with the request JSON; "-" reads stdin.',
    )
    # A plain string for the parser (a model type would be split into per-field flags);
    # validated as a request below.
    json_input: str | None = Field(
        default=None,
        validation_alias=AliasChoices("j", "json"),
        description="Request JSON given inline.",
    )
    output_file: str = Field(
        default=STDIO,
        validation_alias=AliasChoices("o", "output"),
        description='File to write results to; "-" writes to stdout.',
    )

    @field_validator("input_file")
    @classmethod
    def input_file_must_exist(cls, value: str | None) -> str | None:
        if value is not None and value != STDIO and not Path(value).is_file():
            raise ValueError(f"file not found: {value}")
        return value

    @field_validator("output_file")
    @classmethod
    def output_directory_must_exist(cls, value: str) -> str:
        if value != STDIO and not Path(value).parent.is_dir():
            raise ValueError(f"directory not found: {Path(value).parent}")
        return value

    @field_validator("json_input")
    @classmethod
    def json_input_must_be_a_request(cls, value: str | None) -> str | None:
        if value is not None:
            PayloadRequest.model_validate_json(value)
        return value

    @model_validator(mode="after")
    def exactly_one_input(self) -> Self:
        if (self.input_file is None) == (self.json_input is None):
            raise ValueError("pass exactly one of --input or --json")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Arguments come from the command line only; an environment variable named `host`
        # or `output` must not silently change what the tool does.
        return (init_settings,)

    def load_request(self, stdin: TextIO | None = None) -> PayloadRequest:
        if self.json_input is not None:
            return PayloadRequest.model_validate_json(self.json_input)
        if self.input_file == STDIO:
            # Resolved at call time, not as a default argument, so a replaced sys.stdin is used.
            return PayloadRequest.model_validate_json((stdin or sys.stdin).read())
        assert self.input_file is not None  # guaranteed by exactly_one_input
        return PayloadRequest.model_validate_json(Path(self.input_file).read_text(encoding="utf-8"))
