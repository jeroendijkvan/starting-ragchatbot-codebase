import sys
import os
import pytest
from unittest.mock import MagicMock

# Ensure backend/ is on the path so imports like `from vector_store import ...` resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _build_test_app(rag):
    """Minimal FastAPI app mirroring app.py routes with an injected rag mock.

    Defined here rather than importing app.py directly to avoid the StaticFiles
    mount that requires ../frontend to exist in the test environment.
    """
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import Any, List, Optional

    app = FastAPI()

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Any]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag.session_manager.create_session()
            answer, sources = rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def mock_rag_system():
    """Fresh MagicMock of RAGSystem pre-configured with sensible defaults."""
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "test-session-id"
    rag.query.return_value = (
        "This is the answer.",
        [{"label": "Python - Lesson 1", "url": "https://example.com/1"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Introduction to Python", "Advanced ML"],
    }
    return rag


@pytest.fixture
def test_client(mock_rag_system):
    """TestClient wired to the inline test app using the mock_rag_system fixture."""
    from fastapi.testclient import TestClient

    app = _build_test_app(mock_rag_system)
    return TestClient(app)
