import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from web_service.core.config import auth_settings
from web_service.core.database import get_session
from web_service.exception.auth import AuthException
from web_service.model.user import User
from web_utils.auth.jwt_util import decode_token

security_scheme = HTTPBearer()


async def get_user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(token, auth_settings.secret_key)
    except jwt.InvalidTokenError as e:
        raise AuthException(message="token 无效：token无效或已过期") from e

    sub: str | None = payload.get("sub")
    if sub is None:
        raise AuthException(message="token 无效：token无效或已过期")
    user_id = int(sub)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthException(message="token 无效：token无效或已过期")

    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    return await get_user_from_token(credentials.credentials, db)
