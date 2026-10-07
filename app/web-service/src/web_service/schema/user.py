"""用户认证相关的 DTO 定义。

对应模型：web_service.model.user.User
涵盖注册、登录、修改密码以及令牌响应等场景。
"""

from pydantic import Field
from web_service.schema.base import BaseSchema


class UserRegister(BaseSchema):
    """用户注册请求体。"""

    username: str = Field(min_length=1, max_length=100, description="用户名")
    password: str = Field(min_length=6, max_length=100, description="密码")


class UserLogin(BaseSchema):
    """用户登录请求体。"""

    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class ChangePassword(BaseSchema):
    """修改密码请求体。"""

    old_password: str = Field(description="原密码")
    new_password: str = Field(min_length=6, max_length=100, description="新密码")


class UserResponse(BaseSchema):
    """用户简要响应体。"""

    id: int
    username: str


class TokenResponse(BaseSchema):
    """JWT 令牌响应体，登录成功后返回给客户端。"""

    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
