"""MIME 类型工具的单元测试。

测试覆盖：根据文件后缀获取 MIME 类型、MIME 类型常量表。
"""

from web_utils.shared.mime import get_mime_type, IMAGE_MIME, DOC_MIME


class TestGetMimeType:
    """get_mime_type 函数的测试：根据文件后缀返回对应的 MIME 类型。"""

    def test_with_dot(self):
        """验证带点号的后缀能正确返回 MIME 类型。"""
        assert get_mime_type(".png") == "image/png"

    def test_without_dot(self):
        """验证不带点号的后缀也能正确识别。"""
        assert get_mime_type("png") == "image/png"

    def test_uppercase(self):
        """验证大写的后缀会被统一转为小写处理。"""
        assert get_mime_type(".JPG") == "image/jpeg"

    def test_doc_type(self):
        """验证 PDF 文档类型的 MIME 映射。"""
        assert get_mime_type(".pdf") == "application/pdf"

    def test_docx_type(self):
        """验证 DOCX 文档类型的 MIME 映射（较长的 MIME 字符串）。"""
        assert (
            get_mime_type(".docx")
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_unknown_type(self):
        """验证未知后缀返回 None。"""
        assert get_mime_type(".xyz") is None

    def test_empty_string(self):
        """验证空字符串输入返回 None。"""
        assert get_mime_type("") is None


class TestMimeConstants:
    """MIME 类型常量表的测试：验证 IMAGE_MIME 和 DOC_MIME 的数据完整性。"""

    def test_image_mime_not_empty(self):
        """验证图片 MIME 类型表不为空。"""
        assert len(IMAGE_MIME) > 0

    def test_doc_mime_not_empty(self):
        """验证文档 MIME 类型表不为空。"""
        assert len(DOC_MIME) > 0

    def test_all_keys_start_with_dot(self):
        """验证所有 MIME 类型常量的 key 都以点号开头，保持格式一致。"""
        for key in {**IMAGE_MIME, **DOC_MIME}:
            assert key.startswith(".")
