"""JWT 工具函数的单元测试。

测试覆盖：Token 创建（字段、过期时间、唯一性）和 Token 解码（正常、签名错误、过期）。
"""

import jwt
import pytest
from datetime import datetime, timedelta
from web_utils.auth.jwt_util import create_token, decode_token

SECRET = "a-32-byte-long-secret-key-for-testing-hs256"


class TestCreateToken:
    """create_token 函数的测试：验证生成的 JWT Token 包含正确的字段和行为。"""

    def test_returns_string(self):
        """验证返回值是字符串类型。"""
        token = create_token({"sub": "user1"}, SECRET)
        assert isinstance(token, str)

    def test_token_can_be_decoded(self):
        """验证生成的 Token 能用相同密钥解码。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert decoded["sub"] == "user1"

    def test_contains_custom_data(self):
        """验证自定义字段（如 role）被正确写入 Token。"""
        token = create_token({"sub": "user1", "role": "admin"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert decoded["sub"] == "user1"
        assert decoded["role"] == "admin"

    def test_contains_jti(self):
        """验证 Token 包含 jti（JWT ID）字段，用于唯一标识。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert "jti" in decoded
        assert isinstance(decoded["jti"], str)

    def test_contains_iat(self):
        """验证 Token 包含 iat（签发时间）字段。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert "iat" in decoded

    def test_contains_exp(self):
        """验证 Token 包含 exp（过期时间）字段。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert "exp" in decoded

    def test_default_expires_in_2_hours(self):
        """验证默认过期时间为 2 小时（7200 秒）。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        iat = decoded["iat"]
        exp = decoded["exp"]
        assert exp - iat == 7200

    def test_custom_expires_delta(self):
        """验证自定义过期时间生效。"""
        token = create_token(
            {"sub": "user1"}, SECRET, expires_delta=timedelta(minutes=30)
        )
        decoded = decode_token(token, SECRET)
        iat = decoded["iat"]
        exp = decoded["exp"]
        assert exp - iat == 1800

    def test_input_data_is_not_mutated(self):
        """验证传入的 data 字典不会被修改（函数内部做了拷贝）。"""
        data = {"sub": "user1"}
        create_token(data, SECRET)
        assert data == {"sub": "user1"}

    def test_different_tokens_for_same_data(self):
        """验证相同数据每次生成的 Token 不同（因为 jti 随机）。"""
        token1 = create_token({"sub": "user1"}, SECRET)
        token2 = create_token({"sub": "user1"}, SECRET)
        assert token1 != token2


class TestDecodeToken:
    """decode_token 函数的测试：验证解码的正常路径和异常处理。"""

    def test_decodes_valid_token(self):
        """验证有效 Token 能正确解码出原始数据。"""
        token = create_token({"sub": "user1"}, SECRET)
        decoded = decode_token(token, SECRET)
        assert decoded["sub"] == "user1"

    def test_wrong_secret_key_raises_error(self):
        """验证使用错误密钥解码时抛出签名无效异常。"""
        token = create_token({"sub": "user1"}, SECRET)
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(token, "a-wrong-secret-key-that-does-not-match")

    def test_expired_token_raises_error(self):
        """验证过期 Token 解码时抛出过期异常。"""
        token = create_token(
            {"sub": "user1"}, SECRET, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token, SECRET)
