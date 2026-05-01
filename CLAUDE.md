# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Install dependencies (from repo root)
uv sync

# Start the server (runs on http://localhost:8000)
./run.sh

# Or manually from the backend directory
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the repo root with `ANTHROPIC_API_KEY=your_key_here`.

## Architecture

The app is a RAG chatbot that answers questions about course documents. On startup, it reads all `.txt`/`.pdf`/`.docx` files from `docs/`, chunks them, embeds them with `sentence-transformers`, and stores them in ChromaDB. At query time, Claude uses a tool call to search the vector store, then synthesizes an answer.

**Request flow:**
```
Browser → POST /api/query → RAGSystem.query()
  → AIGenerator.generate_response()   # first Claude call
  → Claude emits tool_use: search_course_content
  → CourseSearchTool.execute()        # semantic search via VectorStore
  → AIGenerator._handle_tool_execution()  # second Claude call with results
  → response + sources returned to browser
```

**Key files in `backend/`:**

| File | Role |
|---|---|
| `app.py` | FastAPI entrypoint; mounts frontend static files; loads docs on startup |
| `rag_system.py` | Orchestrator — wires all components together; owns `query()` |
| `ai_generator.py` | Anthropic SDK calls; handles the tool-use agentic loop |
| `vector_store.py` | ChromaDB wrapper; two collections: `course_catalog` (metadata) and `course_content` (chunks) |
| `document_processor.py` | Parses course `.txt` files by header convention, chunks text with overlap |
| `search_tools.py` | `CourseSearchTool` (Anthropic tool definition + execute); `ToolManager` registry |
| `session_manager.py` | In-memory conversation history keyed by session ID |
| `config.py` | Single `Config` dataclass; reads from `.env` |
| `models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |

**Frontend** (`frontend/`) is plain HTML/CSS/JS served as static files by FastAPI — no build step.

## Course document format

Files in `docs/` must follow this convention for the parser to extract structured metadata:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <lesson title>
...
```

Course title doubles as the unique ID in ChromaDB — adding the same title twice is skipped automatically.

## Key configuration knobs (`config.py`)

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model used for generation |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for embeddings |
| `CHUNK_SIZE` | 800 | Max characters per chunk |
| `CHUNK_OVERLAP` | 100 | Overlap characters between chunks |
| `MAX_RESULTS` | 5 | Chunks returned per vector search |
| `MAX_HISTORY` | 2 | Conversation turns retained per session |
| `CHROMA_PATH` | `./chroma_db` | Persistent ChromaDB storage (relative to `backend/`) |

## Adding a new tool

1. Subclass `Tool` in `search_tools.py`, implement `get_tool_definition()` and `execute()`
2. Register it in `RAGSystem.__init__()` via `self.tool_manager.register_tool(your_tool)`
3. The agentic loop in `AIGenerator._handle_tool_execution()` handles multiple tool calls automatically
