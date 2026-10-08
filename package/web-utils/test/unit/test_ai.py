"""AI 聊天模块的单元测试。

测试覆盖：配置类、消息结构、角色枚举、流式对话功能。
使用 mock 替代真实 API 调用，确保测试快速且无外部依赖。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from web_utils.ai.chat import AIChat, AIChatConfig, AIMessage, MessageRole


@pytest.fixture
def config():
    """创建测试用的 AIChatConfig 配置实例。"""
    return AIChatConfig(
        api_key="test-key",
        base_url="https://test.api.com/v1",
        model="test-model",
    )


@pytest.fixture
def chat(config):
    """创建使用 mock 客户端的 AIChat 实例，避免真实 API 调用。"""
    with patch("web_utils.ai.chat.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        return AIChat(config)


class TestAIChatConfig:
    """AIChatConfig 配置类的测试。"""

    def test_defaults(self):
        """验证未提供可选参数时使用默认值。"""
        config = AIChatConfig(api_key="sk-xxx")
        assert config.api_key == "sk-xxx"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o"


class TestAIMessage:
    """AIMessage 消息结构的测试。"""

    def test_create_message(self):
        """验证能正确创建消息并保留 role 和 content。"""
        msg = AIMessage(role=MessageRole.USER, content="你好")
        assert msg.role == MessageRole.USER
        assert msg.content == "你好"

    def test_system_message(self):
        """验证系统消息的 role 值和字符串表示。"""
        msg = AIMessage(role=MessageRole.SYSTEM, content="你是助手")
        assert msg.role == MessageRole.SYSTEM
        assert msg.role.value == "system"

    def test_assistant_message(self):
        """验证助手消息的 role 值和字符串表示。"""
        msg = AIMessage(role=MessageRole.ASSISTANT, content="好的")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.role.value == "assistant"


class TestMessageRole:
    """MessageRole 角色枚举的测试。"""

    def test_values(self):
        """验证各角色的字符串值与 OpenAI API 规范一致。"""
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"

    def test_is_string(self):
        """验证 MessageRole 继承自 str，可直接作为字符串使用。"""
        assert isinstance(MessageRole.USER, str)


class TestChatStream:
    """流式对话 chat_stream 的单元测试，使用 mock 替代真实 API 调用。"""

    @staticmethod
    def _make_chunk(content):
        """构造一个模拟的流式响应 chunk，模拟 OpenAI SDK 返回的数据结构。"""
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = content
        return chunk

    @staticmethod
    def _make_async_stream(chunks):
        """将 chunk 列表包装为异步生成器，模拟 API 的流式返回。"""

        async def _stream():
            for chunk in chunks:
                yield chunk

        return _stream()

    async def test_yields_content(self, chat):
        """验证流式响应能按顺序逐块返回内容。"""
        chunks = [
            self._make_chunk("你好"),
            self._make_chunk("，世界"),
            self._make_chunk("！"),
        ]
        chat._client.chat.completions.create = AsyncMock(
            return_value=self._make_async_stream(chunks)
        )

        messages = [AIMessage(role=MessageRole.USER, content="hello")]
        result = []
        async for text in chat.chat_stream(messages):
            result.append(text)

        assert result == ["你好", "，世界", "！"]

    async def test_passes_model_and_messages(self, chat):
        """验证调用 API 时正确传递了 model、stream 和 messages 参数。"""
        chunk = self._make_chunk("ok")
        chat._client.chat.completions.create = AsyncMock(
            return_value=self._make_async_stream([chunk])
        )

        messages = [
            AIMessage(role=MessageRole.SYSTEM, content="system prompt"),
            AIMessage(role=MessageRole.USER, content="user message"),
        ]

        async for _ in chat.chat_stream(messages):
            pass

        call_kwargs = chat._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["stream"] is True
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ]

    async def test_skips_empty_delta_content(self, chat):
        """验证当 chunk 的 delta.content 为 None 时会被跳过，不 yield 空值。"""
        chunks = [
            self._make_chunk(None),
            self._make_chunk("hello"),
            self._make_chunk(None),
            self._make_chunk(" world"),
        ]
        chat._client.chat.completions.create = AsyncMock(
            return_value=self._make_async_stream(chunks)
        )

        messages = [AIMessage(role=MessageRole.USER, content="hi")]
        result = []
        async for text in chat.chat_stream(messages):
            result.append(text)

        assert result == ["hello", " world"]

    async def test_empty_messages(self, chat):
        """验证传入空消息列表时能正常调用 API。"""
        chunk = self._make_chunk("ok")
        chat._client.chat.completions.create = AsyncMock(
            return_value=self._make_async_stream([chunk])
        )

        async for _ in chat.chat_stream([]):
            pass

        call_kwargs = chat._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == []
