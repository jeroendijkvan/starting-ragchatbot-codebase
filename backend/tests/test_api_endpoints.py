"""
Tests for FastAPI endpoints in app.py.

Uses an inline test app (via conftest._build_test_app) to avoid the static-file
mount that requires ../frontend to exist, and to avoid instantiating a real RAGSystem.
The app mirrors the routes and logic from app.py exactly; only the rag dependency
is swapped for a MagicMock.
"""
import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_on_valid_query(self, test_client):
        resp = test_client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200

    def test_response_shape(self, test_client):
        resp = test_client.post("/api/query", json={"query": "test"})
        body = resp.json()
        assert "answer" in body
        assert "sources" in body
        assert "session_id" in body

    def test_answer_from_rag_is_returned(self, test_client, mock_rag_system):
        mock_rag_system.query.return_value = ("Python is a language.", [])
        resp = test_client.post("/api/query", json={"query": "What is Python?"})
        assert resp.json()["answer"] == "Python is a language."

    def test_sources_from_rag_are_returned(self, test_client, mock_rag_system):
        sources = [{"label": "Python - Lesson 1", "url": "https://example.com/1"}]
        mock_rag_system.query.return_value = ("Answer.", sources)
        resp = test_client.post("/api/query", json={"query": "test"})
        assert resp.json()["sources"] == sources

    def test_auto_creates_session_when_not_provided(self, test_client, mock_rag_system):
        mock_rag_system.session_manager.create_session.return_value = "new-session"
        resp = test_client.post("/api/query", json={"query": "test"})
        assert resp.json()["session_id"] == "new-session"
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_uses_provided_session_id(self, test_client, mock_rag_system):
        resp = test_client.post(
            "/api/query", json={"query": "test", "session_id": "my-session"}
        )
        assert resp.json()["session_id"] == "my-session"
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_string_forwarded_to_rag(self, test_client, mock_rag_system):
        test_client.post("/api/query", json={"query": "specific question"})
        called_query = mock_rag_system.query.call_args[0][0]
        assert called_query == "specific question"

    def test_session_id_forwarded_to_rag(self, test_client, mock_rag_system):
        test_client.post("/api/query", json={"query": "q", "session_id": "s1"})
        called_session = mock_rag_system.query.call_args[0][1]
        assert called_session == "s1"

    def test_missing_query_field_returns_422(self, test_client):
        resp = test_client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_non_json_body_returns_422(self, test_client):
        resp = test_client.post(
            "/api/query",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_rag_exception_returns_500(self, test_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")
        resp = test_client.post("/api/query", json={"query": "test"})
        assert resp.status_code == 500
        assert "DB unavailable" in resp.json()["detail"]

    def test_500_detail_contains_exception_message(self, test_client, mock_rag_system):
        mock_rag_system.query.side_effect = ValueError("embedding model failed")
        resp = test_client.post("/api/query", json={"query": "test"})
        assert "embedding model failed" in resp.json()["detail"]

    def test_empty_sources_list_is_valid(self, test_client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer with no sources.", [])
        resp = test_client.post("/api/query", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, test_client):
        resp = test_client.get("/api/courses")
        assert resp.status_code == 200

    def test_response_shape(self, test_client):
        resp = test_client.get("/api/courses")
        body = resp.json()
        assert "total_courses" in body
        assert "course_titles" in body

    def test_total_courses_count(self, test_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["A", "B", "C"],
        }
        resp = test_client.get("/api/courses")
        assert resp.json()["total_courses"] == 3

    def test_course_titles_list(self, test_client, mock_rag_system):
        titles = ["Introduction to Python", "Advanced ML"]
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": titles,
        }
        resp = test_client.get("/api/courses")
        assert resp.json()["course_titles"] == titles

    def test_empty_catalog_returns_zero(self, test_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        resp = test_client.get("/api/courses")
        assert resp.json()["total_courses"] == 0
        assert resp.json()["course_titles"] == []

    def test_analytics_exception_returns_500(self, test_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("analytics down")
        resp = test_client.get("/api/courses")
        assert resp.status_code == 500
        assert "analytics down" in resp.json()["detail"]

    def test_course_titles_is_a_list(self, test_client):
        resp = test_client.get("/api/courses")
        assert isinstance(resp.json()["course_titles"], list)

    def test_total_courses_is_an_int(self, test_client):
        resp = test_client.get("/api/courses")
        assert isinstance(resp.json()["total_courses"], int)
