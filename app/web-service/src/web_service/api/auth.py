from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.auth import get_current_user
from web_service.core.database import get_session
from web_service.model.user import User
from web_service.schema.user import (
    ChangePassword,
    UserLogin,
    UserRegister,
    TokenResponse,
    UserResponse,
)
from web_service.service import UserService

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await UserService(db).register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await UserService(db).login(data)


@router.get("/me", response_model=UserResponse)
async def profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await UserService(db).profile(current_user)


@router.put("/password", status_code=204)
async def change_password(
    data: ChangePassword,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await UserService(db).change_password(
        current_user, data.old_password, data.new_password
    )
