"""
异常模块。

对外统一导出业务异常基类、数据库异常子类和错误码枚举，
调用方只需通过 ``from web_service.exception import ...`` 即可使用。

文件组织方式（按职责分文件，便于扩展）：
- codes.py      → ErrorCode 枚举（所有子类共享）
- base.py       → BusinessException 基类（所有子类继承）
- database.py   → DatabaseException（数据库层异常子类）

扩展新异常类型的方式：在 exception/ 下新建模块（如 auth.py），
继承 BusinessException 并在本 __init__.py 中追加导出。
"""

from web_service.exception.base import BusinessException
from web_service.exception.codes import ErrorCode
from web_service.exception.database import DatabaseException
from web_service.exception.upload import UploadException
from web_service.exception.auth import AuthException

__all__ = [
    "BusinessException",
    "DatabaseException",
    "UploadException",
    "AuthException",
    "ErrorCode",
]
