"""密码哈希工具的单元测试。

测试覆盖：密码哈希生成和密码验证，基于 bcrypt 算法。
"""

from web_utils.auth.password import hash_password, verify_password


class TestHashPassword:
    """hash_password 函数的测试：验证哈希生成的正确性和安全性特征。"""

    def test_returns_string(self):
        """验证返回值是字符串类型。"""
        result = hash_password("my_password")
        assert isinstance(result, str)

    def test_returns_different_from_input(self):
        """验证哈希值与原始密码不同。"""
        result = hash_password("my_password")
        assert result != "my_password"

    def test_different_passwords_produce_different_hashes(self):
        """验证不同密码产生不同的哈希值。"""
        hash1 = hash_password("password_a")
        hash2 = hash_password("password_b")
        assert hash1 != hash2

    def test_same_password_produces_different_hash_each_time(self):
        """验证相同密码每次哈希结果不同（bcrypt 使用随机 salt）。"""
        hash1 = hash_password("same_password")
        hash2 = hash_password("same_password")
        assert hash1 != hash2


class TestVerifyPassword:
    """verify_password 函数的测试：验证密码校验逻辑。"""

    def test_correct_password_returns_true(self):
        """验证正确密码返回 True。"""
        plain = "secret123"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_wrong_password_returns_false(self):
        """验证错误密码返回 False。"""
        hashed = hash_password("secret123")
        assert verify_password("wrong_password", hashed) is False

    def test_empty_password(self):
        """验证空密码也能正常哈希和校验。"""
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("x", hashed) is False
