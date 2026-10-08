"""文件路径工具的单元测试。

测试覆盖：get_suffix 函数从文件路径中提取后缀的各种场景。
"""

from web_utils.shared.file_util import get_suffix


class TestGetSuffix:
    """get_suffix 函数的测试：从文件名或路径中提取后缀（不含点号，统一小写）。"""

    def test_bare_filename(self):
        """验证纯文件名能正确提取后缀。"""
        assert get_suffix("photo.png") == "png"

    def test_path_with_dirs(self):
        """验证带目录路径的文件名能正确提取后缀，并转为小写。"""
        assert get_suffix("/a/b/c/report.PDF") == "pdf"

    def test_multiple_dots(self):
        """验证多个点号的文件名取最后一个后缀。"""
        assert get_suffix("archive.tar.gz") == "gz"

    def test_no_extension(self):
        """验证无后缀的文件名返回 None。"""
        assert get_suffix("noext") is None

    def test_dotfile_hidden_no_extension(self):
        """验证以点号开头的隐藏文件（无其他后缀）返回 None。"""
        assert get_suffix(".hidden") is None

    def test_empty_string(self):
        """验证空字符串输入返回 None。"""
        assert get_suffix("") is None
