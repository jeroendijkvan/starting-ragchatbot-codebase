"""
Tests for RAGSystem.query() — the full request pipeline.

Covers:
- query() returns (str, list) — never raises
- AI generator is always called with tools and tool_manager
- When Claude calls search_course_content, the tool executes and results flow back
- The tool result contains real content (not "Search error" or empty)
- Session history is passed on follow-up queries
- ChromaDB search handles the where=None case without crashing
"""
import sys
import os
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag_system import RAGSystem
from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Config:
    ANTHROPIC_API_KEY = "test-key"
    ANTHROPIC_MODEL = "test-model"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    MAX_RESULTS = 5
    MAX_HISTORY = 2
    CHROMA_PATH = None  # overridden per test


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


def _tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="t1"):
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [
        _content_block(
            "tool_use",
            name=tool_name,
            input=tool_input or {"query": "Python"},
            id=tool_id,
        )
    ]
    return resp


# ---------------------------------------------------------------------------
# RAGSystem.query() unit tests (AI generator fully mocked)
# ---------------------------------------------------------------------------

class TestRAGSystemQueryUnit(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        cfg = _Config()
        cfg.CHROMA_PATH = self.temp_dir
        with patch("ai_generator.anthropic.Anthropic"):
            self.rag = RAGSystem(cfg)
        # Replace AI generator with a simple mock
        self.mock_gen = MagicMock()
        self.mock_gen.generate_response.return_value = "Test answer."
        self.rag.ai_generator = self.mock_gen

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_returns_string_and_list(self):
        response, sources = self.rag.query("What is Python?")
        self.assertIsInstance(response, str)
        self.assertIsInstance(sources, list)

    def test_query_does_not_raise_on_content_question(self):
        try:
            self.rag.query("Tell me about Python variables")
        except Exception as e:
            self.fail(f"rag.query() raised {type(e).__name__}: {e}")

    def test_ai_generator_receives_tools(self):
        self.rag.query("What is Python?")
        kw = self.mock_gen.generate_response.call_args[1]
        self.assertIn("tools", kw)
        self.assertGreater(len(kw["tools"]), 0,
            "No tools passed to AI generator — search tool will never be called.")

    def test_ai_generator_receives_tool_manager(self):
        self.rag.query("What is Python?")
        kw = self.mock_gen.generate_response.call_args[1]
        self.assertIn("tool_manager", kw)
        self.assertIsNotNone(kw["tool_manager"],
            "tool_manager is None — tool execution will be skipped.")

    def test_tool_definitions_include_search_course_content(self):
        self.rag.query("What is Python?")
        kw = self.mock_gen.generate_response.call_args[1]
        tool_names = [t.get("name") for t in kw["tools"]]
        self.assertIn("search_course_content", tool_names,
            "search_course_content not registered in tool definitions.")

    def test_response_text_returned_to_caller(self):
        self.mock_gen.generate_response.return_value = "Python is great."
        response, _ = self.rag.query("What is Python?")
        self.assertEqual(response, "Python is great.")

    def test_session_history_passed_on_second_query(self):
        session_id = self.rag.session_manager.create_session()
        self.rag.query("Hello", session_id=session_id)
        self.rag.query("Tell me more", session_id=session_id)
        kw = self.mock_gen.generate_response.call_args[1]
        # After the first exchange there should be history
        self.assertIn("conversation_history", kw)
        self.assertIsNotNone(
            kw["conversation_history"],
            "Conversation history not forwarded on second query.",
        )

    def test_sources_reset_between_queries(self):
        """last_sources from a previous query must not bleed into the next."""
        # Manually set some stale sources
        self.rag.search_tool.last_sources = [{"label": "Stale", "url": None}]
        _, sources = self.rag.query("new question")
        # After reset, sources should be empty (no real search happened via mock)
        self.assertEqual(sources, [])


# ---------------------------------------------------------------------------
# Integration tests — real ChromaDB + mocked Anthropic API
# ---------------------------------------------------------------------------

class TestRAGSystemToolPipeline(unittest.TestCase):
    """
    End-to-end pipeline tests: Claude emits tool_use → tool executes against
    real ChromaDB → result flows back in the second API call.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cfg = _Config()
        cfg.CHROMA_PATH = cls.temp_dir
        with patch("ai_generator.anthropic.Anthropic"):
            cls.rag = RAGSystem(cfg)
        # Seed course data
        course = Course(
            title="Introduction to Python",
            course_link="https://example.com/python",
            instructor="Test Instructor",
            lessons=[
                Lesson(lesson_number=1, title="Basics", lesson_link="https://example.com/1"),
                Lesson(lesson_number=2, title="Functions", lesson_link="https://example.com/2"),
            ],
        )
        cls.rag.vector_store.add_course_metadata(course)
        cls.rag.vector_store.add_course_content([
            CourseChunk(
                content="Python variables store data. You assign them with the = operator.",
                course_title="Introduction to Python",
                lesson_number=1,
                chunk_index=0,
            ),
            CourseChunk(
                content="Functions in Python are defined with the def keyword.",
                course_title="Introduction to Python",
                lesson_number=2,
                chunk_index=1,
            ),
        ])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _set_api_responses(self, first, second):
        self.rag.ai_generator.client.messages.create.side_effect = [first, second]

    def test_tool_use_loop_completes_without_exception(self):
        self._set_api_responses(
            _tool_use_response("search_course_content", {"query": "Python variables"}),
            _text_response("Python variables store data."),
        )
        try:
            response, _ = self.rag.query("Tell me about Python variables")
        except Exception as e:
            self.fail(f"query() raised {type(e).__name__}: {e}")
        self.assertEqual(response, "Python variables store data.")

    def test_tool_result_is_non_empty_content(self):
        """The search tool must return actual content, not an error string."""
        captured = []

        def api_side_effect(**kwargs):
            messages = kwargs.get("messages", [])
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    for item in msg["content"]:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            captured.append(item["content"])
            return _text_response("Synthesized.")

        first_call = True
        original = self.rag.ai_generator.client.messages.create

        def side_effect(**kwargs):
            nonlocal first_call
            if first_call:
                first_call = False
                return _tool_use_response("search_course_content", {"query": "Python variables"})
            return api_side_effect(**kwargs)

        self.rag.ai_generator.client.messages.create.side_effect = side_effect

        self.rag.query("What are Python variables?")

        self.assertGreater(len(captured), 0,
            "No tool_result found in second API call — search output never reached Claude.")
        for content in captured:
            self.assertNotIn("Search error", content,
                f"Tool returned an error instead of course content: {content}")
            self.assertNotEqual(content.strip(), "",
                "Tool returned empty content.")

    def test_vector_store_bare_search_returns_results(self):
        """VectorStore.search() with no filters (where=None) must not error."""
        result = self.rag.vector_store.search(query="Python variables")
        self.assertIsNone(result.error,
            f"search() with no filter returned error: {result.error}")
        self.assertFalse(result.is_empty(),
            "Search returned no results even though content was seeded.")

    def test_vector_store_search_with_course_filter(self):
        result = self.rag.vector_store.search(
            query="variables", course_name="Introduction to Python"
        )
        self.assertIsNone(result.error,
            f"search() with course filter returned error: {result.error}")

    def test_vector_store_search_with_lesson_filter(self):
        result = self.rag.vector_store.search(query="variables", lesson_number=1)
        self.assertIsNone(result.error,
            f"search() with lesson_number filter returned error: {result.error}")

    def test_vector_store_search_with_combined_filters(self):
        result = self.rag.vector_store.search(
            query="variables",
            course_name="Introduction to Python",
            lesson_number=1,
        )
        self.assertIsNone(result.error,
            f"search() with combined filters returned error: {result.error}")


# ---------------------------------------------------------------------------
# Document processor chunk context tests
# ---------------------------------------------------------------------------

class TestDocumentProcessorChunkContext(unittest.TestCase):
    """
    Verifies that ALL chunks (not just the first) from every lesson
    carry course/lesson metadata in their content.
    Without this, mid-lesson chunks are unidentifiable during retrieval.
    """

    def setUp(self):
        from document_processor import DocumentProcessor
        self.processor = DocumentProcessor(chunk_size=100, chunk_overlap=10)

    def _make_course_file(self, content):
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write(content)
        f.close()
        return f.name

    # Sentences that genuinely split at chunk_size=100 (each ~25 chars, so 4+ per chunk)
    _MULTI_SENTENCE = (
        "Python is a language. It is high level. You can use it for scripting. "
        "It runs on many platforms. Variables hold data. Functions encapsulate logic. "
        "Classes define objects. Modules organize code. Packages group modules."
    )

    def test_non_last_lesson_all_chunks_have_course_context(self):
        """
        Each chunk from non-last lessons must carry course/lesson context.
        Bug (pre-fix): only the first chunk got context; subsequent chunks were anonymous.
        """
        course_text = (
            "Course Title: Test Course\n"
            "Course Link: https://example.com\n"
            "Course Instructor: Test\n"
            "\n"
            f"Lesson 1: First Lesson\n{self._MULTI_SENTENCE}\n"
            "Lesson 2: Second Lesson\nShort content.\n"
        )
        path = self._make_course_file(course_text)
        try:
            _, chunks = self.processor.process_course_document(path)
            lesson1_chunks = [c for c in chunks if c.lesson_number == 1]
            self.assertGreater(len(lesson1_chunks), 1,
                "Need multiple chunks for this test to be meaningful — "
                "increase _MULTI_SENTENCE or lower chunk_size.")
            for i, chunk in enumerate(lesson1_chunks):
                has_context = (
                    "Test Course" in chunk.content
                    or "Lesson 1" in chunk.content
                )
                self.assertTrue(has_context,
                    f"Lesson 1 chunk {i} has no course/lesson context: {chunk.content[:80]!r}")
        finally:
            os.unlink(path)

    def test_last_lesson_all_chunks_have_course_context(self):
        """Last-lesson chunks should all carry course/lesson context."""
        course_text = (
            "Course Title: Test Course\n"
            "Course Link: https://example.com\n"
            "Course Instructor: Test\n"
            "\n"
            f"Lesson 1: Only Lesson\n{self._MULTI_SENTENCE}\n"
        )
        path = self._make_course_file(course_text)
        try:
            _, chunks = self.processor.process_course_document(path)
            self.assertGreater(len(chunks), 1,
                "Need multiple chunks for this test to be meaningful.")
            for i, chunk in enumerate(chunks):
                has_context = (
                    "Test Course" in chunk.content
                    or "Lesson 1" in chunk.content
                )
                self.assertTrue(has_context,
                    f"Last-lesson chunk {i} missing context: {chunk.content[:80]!r}")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
