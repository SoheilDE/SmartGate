from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth.db import create_user, issue_api_key, verify_user

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=201)
def register(body: AuthRequest):
    created = create_user(body.username, body.password)
    if not created:
        raise HTTPException(status_code=409, detail="Username already exists")
    return {"message": "Account created. Ask an admin to enable your username before making LLM requests."}


@router.post("/login")
def login(body: AuthRequest):
    if not verify_user(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    key = issue_api_key(body.username)
    return {"api_key": key, "expires_in": "24h"}
