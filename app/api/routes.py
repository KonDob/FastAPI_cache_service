"""HTTP routes for payload create / read."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.services import payload as payload_service

router = APIRouter(prefix="/payload", tags=["payload"])


class PayloadCreate(BaseModel):
    list_1: list[str] = Field(..., min_length=1)
    list_2: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def lists_must_match_length(self) -> "PayloadCreate":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreateResponse(BaseModel):
    id: UUID
    message: str = "Payload created successfully"


class PayloadReadResponse(BaseModel):
    output: str


@router.post(
    "",
    response_model=PayloadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payload(body: PayloadCreate) -> PayloadCreateResponse:
    record_id = payload_service.create_payload(body.list_1, body.list_2)
    return PayloadCreateResponse(id=record_id)


@router.get("/{payload_id}", response_model=PayloadReadResponse)
def read_payload(payload_id: UUID) -> PayloadReadResponse:
    output = payload_service.get_payload(payload_id)
    if output is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payload not found",
        )
    return PayloadReadResponse(output=output)
