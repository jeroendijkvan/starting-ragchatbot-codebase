"""
Tests for CourseSearchTool.execute() in search_tools.py.

Covers:
- Unit tests with mocked VectorStore (fast, no I/O)
- Integration tests with a real ChromaDB in a temp directory
"""
import sys
import os
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vector_store import SearchResults, VectorStore
from search_tools import CourseSearchTool, ToolManager
from models import Course, Lesson, CourseChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _results(docs, metas):
    return SearchResults(
        documents=docs,
        metadata=metas,
        distances=[0.1] * len(docs),
    )


def _mock_store(search_return=None):
    store = MagicMock()
    store.get_lesson_link.return_value = None
    if search_return is not None:
        store.search.return_value = search_return
    return store


# ---------------------------------------------------------------------------
# Unit tests — mocked VectorStore
# ---------------------------------------------------------------------------

class TestCourseSearchToolExecuteUnit(unittest.TestCase):

    def _tool(self, search_return):
        store = _mock_store(search_return)
        return CourseSearchTool(store), store

    # --- happy-path formatting ---

    def test_result_includes_course_and_lesson_header(self):
        tool, _ = self._tool(_results(
            docs=["Python is a language."],
            metas=[{"course_title": "Python Basics", "lesson_number": 1}],
        ))
        result = tool.execute(query="What is Python?")
        self.assertIn("[Python Basics - Lesson 1]", result)
        self.assertIn("Python is a language.", result)

    def test_result_without_lesson_number_omits_lesson_from_header(self):
        tool, _ = self._tool(_results(
            docs=["Some content."],
            metas=[{"course_title": "General Course"}],
        ))
        result = tool.execute(query="something")
        self.assertIn("[General Course]", result)
        self.assertNotIn("Lesson", result)

    def test_multiple_results_are_separated(self):
        tool, _ = self._tool(_results(
            docs=["Chunk A", "Chunk B"],
            metas=[
                {"course_title": "Course", "lesson_number": 1},
                {"course_title": "Course", "lesson_number": 2},
            ],
        ))
        result = tool.execute(query="topic")
        self.assertIn("Chunk A", result)
        self.assertIn("Chunk B", result)

    # --- empty / error cases ---

    def test_no_results_returns_descriptive_message(self):
        tool, _ = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        result = tool.execute(query="nonexistent topic")
        self.assertIn("No relevant content found", result)

    def test_no_results_with_course_filter_names_the_course(self):
        tool, _ = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        result = tool.execute(query="topic", course_name="Python Basics")
        self.assertIn("No relevant content found", result)
        self.assertIn("Python Basics", result)

    def test_no_results_with_lesson_filter_names_the_lesson(self):
        tool, _ = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        result = tool.execute(query="topic", lesson_number=3)
        self.assertIn("No relevant content found", result)
        self.assertIn("lesson 3", result.lower())

    def test_store_error_is_propagated_as_string(self):
        tool, _ = self._tool(SearchResults.empty("Search error: collection has 0 elements"))
        result = tool.execute(query="anything")
        self.assertIn("Search error", result)

    # --- filter forwarding ---

    def test_passes_query_course_and_lesson_to_store(self):
        tool, store = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        tool.execute(query="topic", course_name="ML Course", lesson_number=3)
        store.search.assert_called_once_with(
            query="topic",
            course_name="ML Course",
            lesson_number=3,
        )

    def test_passes_none_filters_when_not_specified(self):
        tool, store = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        tool.execute(query="bare query")
        store.search.assert_called_once_with(
            query="bare query",
            course_name=None,
            lesson_number=None,
        )

    # --- source tracking ---

    def test_last_sources_populated_after_search(self):
        store = _mock_store(_results(
            docs=["Content"],
            metas=[{"course_title": "AI Course", "lesson_number": 2}],
        ))
        store.get_lesson_link.return_value = "https://example.com/lesson/2"
        tool = CourseSearchTool(store)
        tool.execute(query="AI topic")
        self.assertEqual(len(tool.last_sources), 1)
        self.assertEqual(tool.last_sources[0]["label"], "AI Course - Lesson 2")
        self.assertEqual(tool.last_sources[0]["url"], "https://example.com/lesson/2")

    def test_sources_deduplicated_across_chunks(self):
        tool, _ = self._tool(_results(
            docs=["Chunk 1", "Chunk 2", "Chunk 3"],
            metas=[
                {"course_title": "Python", "lesson_number": 1},
                {"course_title": "Python", "lesson_number": 1},
                {"course_title": "Python", "lesson_number": 2},
            ],
        ))
        tool.execute(query="Python")
        self.assertEqual(len(tool.last_sources), 2)

    def test_last_sources_empty_when_no_results(self):
        tool, _ = self._tool(SearchResults(documents=[], metadata=[], distances=[]))
        tool.execute(query="nothing")
        self.assertEqual(tool.last_sources, [])


# ---------------------------------------------------------------------------
# Integration tests — real ChromaDB in a temp directory
# ---------------------------------------------------------------------------

class TestCourseSearchToolIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.store = VectorStore(
            chroma_path=cls.temp_dir,
            embedding_model="all-MiniLM-L6-v2",
            max_results=5,
        )
        course = Course(
            title="Test Python Course",
            course_link="https://example.com/python",
            instructor="Test Instructor",
            lessons=[
                Lesson(lesson_number=1, title="Intro to Python", lesson_link="https://example.com/1"),
                Lesson(lesson_number=2, title="Functions", lesson_link="https://example.com/2"),
            ],
        )
        cls.store.add_course_metadata(course)
        cls.store.add_course_content([
            CourseChunk(content="Python is a high-level programming language.", course_title="Test Python Course", lesson_number=1, chunk_index=0),
            CourseChunk(content="Functions are reusable blocks of code.", course_title="Test Python Course", lesson_number=2, chunk_index=1),
            CourseChunk(content="Variables store data values in Python.", course_title="Test Python Course", lesson_number=1, chunk_index=2),
        ])
        cls.tool = CourseSearchTool(cls.store)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_bare_search_returns_content_without_error(self):
        """Search with no filters must not return a Search error."""
        result = self.tool.execute(query="What is Python?")
        self.assertNotIn("Search error", result, f"Got error: {result}")
        self.assertNotIn("No relevant content found", result)
        self.assertIn("Python", result)

    def test_search_with_valid_course_name_returns_content(self):
        result = self.tool.execute(query="programming", course_name="Test Python Course")
        self.assertNotIn("Search error", result, f"Got error: {result}")

    def test_search_with_partial_course_name_resolves_correctly(self):
        result = self.tool.execute(query="programming", course_name="Python")
        self.assertNotIn("Search error", result, f"Got error: {result}")

    def test_search_with_lesson_number_only_returns_content(self):
        result = self.tool.execute(query="programming", lesson_number=1)
        self.assertNotIn("Search error", result, f"Got error: {result}")

    def test_search_with_both_filters_returns_content(self):
        result = self.tool.execute(query="programming", course_name="Python", lesson_number=1)
        self.assertNotIn("Search error", result, f"Got error: {result}")

    def test_nonexistent_course_gives_clear_message(self):
        result = self.tool.execute(query="programming", course_name="Nonexistent XYZ 99999")
        self.assertIn("No course found", result)

    def test_tool_manager_executes_search_tool(self):
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(self.store))
        result = manager.execute_tool("search_course_content", query="Python")
        self.assertNotIn("Tool 'search_course_content' not found", result)
        self.assertNotIn("Search error", result)


if __name__ == "__main__":
    unittest.main()
