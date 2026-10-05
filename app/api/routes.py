"""HTTP routes for payload create / read."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.db.session import SessionDep
from app.services import payload as payload_service
from app.services.transformer import TransformerDep

router = APIRouter(prefix="/payload", tags=["payload"])


# Bounds keep a single request from overloading the transformer and the database:
# one request's new strings go to the cache in a single INSERT, and PostgreSQL caps
# the number of bind parameters per statement.
MAX_ITEMS_PER_LIST = 1000
MAX_STRING_LENGTH = 1000

BoundedString = Annotated[str, Field(max_length=MAX_STRING_LENGTH)]
BoundedList = Annotated[list[BoundedString], Field(min_length=1, max_length=MAX_ITEMS_PER_LIST)]


class PayloadCreate(BaseModel):
    list_1: BoundedList
    list_2: BoundedList

    @model_validator(mode="after")
    def lists_must_match_length(self) -> "PayloadCreate":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreateResponse(BaseModel):
    id: UUID
    message: str


class PayloadReadResponse(BaseModel):
    output: str


@router.post(
    "",
    response_model=PayloadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": PayloadCreateResponse,
            "description": "Payload for this input already exists; its identifier is reused.",
        },
    },
)
def create_payload(
    body: PayloadCreate,
    response: Response,
    session: SessionDep,
    transformer: TransformerDep,
) -> PayloadCreateResponse:
    result = payload_service.create_payload(session, transformer, body.list_1, body.list_2)
    # 201 vs 200 tells clients whether a new resource appeared, while POST stays idempotent.
    if not result.created:
        response.status_code = status.HTTP_200_OK
        return PayloadCreateResponse(id=result.id, message="Payload already exists")
    return PayloadCreateResponse(id=result.id, message="Payload created")


@router.get("/{payload_id}", response_model=PayloadReadResponse)
def read_payload(payload_id: UUID, session: SessionDep) -> PayloadReadResponse:
    output = payload_service.get_payload(session, payload_id)
    if output is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payload not found",
        )
    return PayloadReadResponse(output=output)
