"""
跨域资源共享（CORS）中间件。

基于 Starlette 内置的 CORSMiddleware，从 config.cors_settings 读取配置。
所有参数均可通过 .env 文件中以 CORS_ 开头的变量进行配置：
    - CORS_ORIGINS        允许的源（白名单），逗号分隔
    - CORS_METHODS        允许的 HTTP 方法，逗号分隔
    - CORS_HEADERS        允许的请求头，逗号分隔
    - CORS_CREDENTIALS    是否允许携带凭证（true/false）
    - CORS_EXPOSE_HEADERS 暴露给前端的响应头，逗号分隔

注册顺序说明：CORS 中间件必须位于最外层（MIDDLEWARES 列表最后），
这样预检 OPTIONS 请求可以在最外层被快速拦截并返回，无需经过
统一响应包装、耗时统计等内层中间件处理。
"""

from starlette.middleware.cors import CORSMiddleware
from web_service.core.config import cors_settings

# 构造 CORSMiddleware 所需的参数
_CORS_KWARGS = {
    "allow_origins": cors_settings.allow_origins,
    "allow_credentials": cors_settings.allow_credentials,
    "allow_methods": cors_settings.allow_methods,
    "allow_headers": cors_settings.allow_headers,
    "expose_headers": cors_settings.expose_headers,
}

MIDDLEWARE = (CORSMiddleware, _CORS_KWARGS)
