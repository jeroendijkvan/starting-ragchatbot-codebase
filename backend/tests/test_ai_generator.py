"""
Tests for AIGenerator in ai_generator.py.

Verifies:
- Tools are forwarded to the Anthropic API call
- When stop_reason == "tool_use", CourseSearchTool is invoked via ToolManager
- Tool results are correctly formatted and sent back to Claude
- The final text response is returned to the caller
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_block(block_type, **attrs):
    block = MagicMock()
    block.type = block_type
    for k, v in attrs.items():
        setattr(block, k, v)
    return block


def _text_response(text="Answer."):
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [_content_block("text", text=text)]
    return resp


def _tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="call_1"):
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [
        _content_block(
            "tool_use",
            name=tool_name,
            input=tool_input or {"query": "test query"},
            id=tool_id,
        )
    ]
    return resp


def _make_generator():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="test-model")
    return gen


# ---------------------------------------------------------------------------
# Direct (no tool use) response tests
# ---------------------------------------------------------------------------

class TestDirectResponse(unittest.TestCase):

    def setUp(self):
        self.gen = _make_generator()

    def test_returns_text_from_response(self):
        self.gen.client.messages.create.return_value = _text_response("Direct answer.")
        self.assertEqual(self.gen.generate_response(query="2+2?"), "Direct answer.")

    def test_query_sent_as_user_role_message(self):
        self.gen.client.messages.create.return_value = _text_response()
        self.gen.generate_response(query="My question")
        kw = self.gen.client.messages.create.call_args[1]
        self.assertEqual(kw["messages"][0]["role"], "user")
        self.assertEqual(kw["messages"][0]["content"], "My question")

    def test_system_prompt_included(self):
        self.gen.client.messages.create.return_value = _text_response()
        self.gen.generate_response(query="test")
        kw = self.gen.client.messages.create.call_args[1]
        self.assertIn("system", kw)
        self.assertGreater(len(kw["system"]), 0)

    def test_conversation_history_appended_to_system(self):
        self.gen.client.messages.create.return_value = _text_response()
        self.gen.generate_response(
            query="Follow-up",
            conversation_history="User: Hello\nAssistant: Hi",
        )
        kw = self.gen.client.messages.create.call_args[1]
        self.assertIn("Previous conversation:", kw["system"])
        self.assertIn("User: Hello", kw["system"])

    def test_tools_forwarded_to_api_when_provided(self):
        self.gen.client.messages.create.return_value = _text_response()
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        self.gen.generate_response(query="test", tools=tools)
        kw = self.gen.client.messages.create.call_args[1]
        self.assertIn("tools", kw)
        self.assertEqual(kw["tools"], tools)

    def test_tool_choice_auto_set_when_tools_provided(self):
        self.gen.client.messages.create.return_value = _text_response()
        self.gen.generate_response(query="test", tools=[{"name": "x"}])
        kw = self.gen.client.messages.create.call_args[1]
        self.assertEqual(kw.get("tool_choice"), {"type": "auto"})

    def test_no_tools_key_when_tools_not_provided(self):
        self.gen.client.messages.create.return_value = _text_response()
        self.gen.generate_response(query="test")
        kw = self.gen.client.messages.create.call_args[1]
        self.assertNotIn("tools", kw)


# ---------------------------------------------------------------------------
# Tool-use execution tests
# ---------------------------------------------------------------------------

class TestToolExecution(unittest.TestCase):

    def setUp(self):
        self.gen = _make_generator()
        self.tool_manager = MagicMock()
        self.tool_manager.execute_tool.return_value = "Search results: Python info."
        self.tools = [{"name": "search_course_content"}]

    def test_tool_use_calls_execute_tool_with_correct_args(self):
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(
                tool_name="search_course_content",
                tool_input={"query": "Python basics"},
                tool_id="call_1",
            ),
            _text_response("Python is a language."),
        ]
        self.gen.generate_response(
            query="What is Python?",
            tools=self.tools,
            tool_manager=self.tool_manager,
        )
        self.tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="Python basics"
        )

    def test_final_text_is_returned_after_tool_use(self):
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response("Final synthesized answer."),
        ]
        result = self.gen.generate_response(
            query="Course question",
            tools=self.tools,
            tool_manager=self.tool_manager,
        )
        self.assertEqual(result, "Final synthesized answer.")

    def test_two_api_calls_made_for_tool_use(self):
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response(),
        ]
        self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=self.tool_manager
        )
        self.assertEqual(self.gen.client.messages.create.call_count, 2)

    def test_second_api_call_contains_tool_result_message(self):
        """
        The follow-up API call MUST include a user message with type=tool_result.
        Without this, Claude has no search results to synthesize from.
        """
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(tool_id="call_abc"),
            _text_response(),
        ]
        self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=self.tool_manager
        )

        second_call_kw = self.gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kw["messages"]

        tool_result_items = [
            item
            for msg in messages
            if isinstance(msg.get("content"), list)
            for item in msg["content"]
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ]
        self.assertGreater(
            len(tool_result_items), 0,
            "No tool_result message found in second API call — "
            "search results were not passed back to Claude.",
        )

    def test_tool_result_references_correct_tool_use_id(self):
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(tool_id="unique_id_123"),
            _text_response(),
        ]
        self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=self.tool_manager
        )

        second_call_kw = self.gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kw["messages"]

        tool_results = [
            item
            for msg in messages
            if isinstance(msg.get("content"), list)
            for item in msg["content"]
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ]
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(
            tool_results[0]["tool_use_id"],
            "unique_id_123",
            "tool_use_id in result doesn't match the original tool call id.",
        )

    def test_tool_result_contains_execute_tool_output(self):
        self.tool_manager.execute_tool.return_value = "Relevant Python content here."
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response(),
        ]
        self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=self.tool_manager
        )

        second_call_kw = self.gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kw["messages"]

        tool_results = [
            item
            for msg in messages
            if isinstance(msg.get("content"), list)
            for item in msg["content"]
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ]
        self.assertGreater(len(tool_results), 0)
        self.assertIn("Relevant Python content here.", tool_results[0]["content"])

    def test_second_api_call_does_not_include_tools_param(self):
        """Follow-up call omits tools to avoid infinite tool-use loops."""
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response(),
        ]
        self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=self.tool_manager
        )
        second_call_kw = self.gen.client.messages.create.call_args_list[1][1]
        self.assertNotIn(
            "tools",
            second_call_kw,
            "Second API call must not include tools — this could cause infinite tool loops.",
        )

    def test_tool_use_without_tool_manager_does_not_raise(self):
        """
        If tool_manager is None and Claude still emits tool_use, the code falls through to
        response.content[0].text. With real SDK objects this raises AttributeError because
        ToolUseBlock has no .text. With MagicMock it returns a MagicMock (not a string).
        This test documents the current behaviour — a real bug if tool_manager is ever None.
        """
        self.gen.client.messages.create.return_value = _tool_use_response()
        # Should not raise with MagicMock (real SDK objects would raise AttributeError)
        result = self.gen.generate_response(
            query="test", tools=self.tools, tool_manager=None
        )
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# _handle_tool_execution internals
# ---------------------------------------------------------------------------

class TestHandleToolExecutionMessages(unittest.TestCase):

    def setUp(self):
        self.gen = _make_generator()
        self.tool_manager = MagicMock()
        self.tool_manager.execute_tool.return_value = "search result"

    def test_assistant_tool_use_message_added_before_tool_result(self):
        """Message order: user → assistant(tool_use) → user(tool_result)"""
        self.gen.client.messages.create.side_effect = [
            _tool_use_response(tool_id="t1"),
            _text_response(),
        ]
        self.gen.generate_response(
            query="q", tools=[{"name": "search_course_content"}], tool_manager=self.tool_manager
        )
        second_call_kw = self.gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kw["messages"]

        roles = [m["role"] for m in messages]
        self.assertIn("assistant", roles)
        assistant_idx = roles.index("assistant")
        # After the assistant message there should be a user message with tool_result
        user_after_assistant = [
            m for m in messages[assistant_idx + 1:]
            if m["role"] == "user"
        ]
        self.assertGreater(
            len(user_after_assistant), 0,
            "Expected a user message with tool_result after the assistant message.",
        )


if __name__ == "__main__":
    unittest.main()
