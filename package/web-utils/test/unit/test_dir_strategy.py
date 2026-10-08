"""上传目录策略的单元测试。

测试覆盖：两种文件存储路径生成策略——按日期分目录和扁平目录。
"""

from datetime import datetime
from unittest.mock import patch
from web_utils.upload.dir_strategy import date_uuid_strategy, flat_uuid_strategy


class TestDateUuidStrategy:
    """date_uuid_strategy 的测试：生成形如 uploads/YYYY/MM/DD/ 的路径。"""

    def test_returns_upload_path_with_date(self):
        """验证生成的路径包含当前日期的年/月/日。"""
        with patch("web_utils.upload.dir_strategy.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 6, 26, 10, 30, 0)
            result = date_uuid_strategy()
        assert result == "uploads/2025/06/26/"

    def test_single_digit_month_day_padded(self):
        """验证月和日为单位数时自动补零（如 01、05）。"""
        with patch("web_utils.upload.dir_strategy.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 5, 10, 30, 0)
            result = date_uuid_strategy()
        assert result == "uploads/2025/01/05/"

    def test_ends_with_slash(self):
        """验证路径以斜杠结尾，便于拼接文件名。"""
        with patch("web_utils.upload.dir_strategy.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 6, 26, 10, 30, 0)
            result = date_uuid_strategy()
        assert result.endswith("/")


class TestFlatUuidStrategy:
    """flat_uuid_strategy 的测试：所有文件统一存放在 uploads/ 下。"""

    def test_returns_flat_path(self):
        """验证扁平策略返回固定路径 uploads/。"""
        result = flat_uuid_strategy()
        assert result == "uploads/"

    def test_ends_with_slash(self):
        """验证路径以斜杠结尾。"""
        result = flat_uuid_strategy()
        assert result.endswith("/")
