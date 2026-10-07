from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from web_service.core.config import auth_settings
from web_service.exception import DatabaseException, AuthException, ErrorCode
from web_service.model.setting_item import SettingItem
from web_service.model.user import User
from web_service.schema.user import UserLogin, UserRegister, TokenResponse, UserResponse
from web_service.service import BaseService
from web_utils.auth.jwt_util import create_token
from web_utils.auth.password import hash_password, verify_password


class UserService(BaseService):
    async def register(self, data: UserRegister) -> UserResponse:
        existing = await self.session.scalar(
            select(User).where(User.username == data.username)
        )
        if existing is not None:
            raise DatabaseException(
                error_code=ErrorCode.CONFLICT, message="注册失败：用户名已存在"
            )

        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
        )
        try:
            self.session.add(user)
            await self.session.flush()
        except IntegrityError as e:
            raise DatabaseException(
                message="注册失败：用户名已存在",
                detail=str(e),
                original_error=e,
            ) from e

        return UserResponse(id=user.id, username=user.username)

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self.session.scalar(
            select(User).where(User.username == data.username)
        )
        if user is None or not verify_password(data.password, user.password_hash):
            raise AuthException(message="登录失败：用户名或密码错误")

        expire_setting = await self.session.scalar(
            select(SettingItem.value).where(SettingItem.key == "jwt_expire_minutes")
        )
        expire_minutes = int(expire_setting) if expire_setting else 120

        token = create_token(
            {"sub": user.id},
            auth_settings.secret_key,
            expires_delta=timedelta(minutes=expire_minutes),
        )
        return TokenResponse(access_token=token)

    async def profile(self, user: User) -> UserResponse:
        return UserResponse(id=user.id, username=user.username)

    async def change_password(
        self, user: User, old_password: str, new_password: str
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise AuthException(message="修改密码失败：原密码错误")

        user.password_hash = hash_password(new_password)
        self.session.add(user)
        await self.session.flush()
