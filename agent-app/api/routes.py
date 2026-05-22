from fastapi import APIRouter
from pydantic import BaseModel

from workflows.access_workflow import run_access_workflow

router = APIRouter()


class AccessRequest(BaseModel):
    request: str


@router.post("/access/request")
def request_access(payload: AccessRequest):

    response = run_access_workflow(payload.request)

    return {
        "success": True,
        "response": response
    }