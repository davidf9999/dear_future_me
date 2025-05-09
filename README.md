# Dear Future Me

## An AI-driven future-self coaching system for suicide prevention

---

## 📖 Overview

`Dear Future Me` provides a compassionate conversational interface where users chat with an AI persona representing their own positive, thriving future selves. It combines:

| Capability                               | Notes                                                                                                |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Crisis Detection**                     | Detects self-harm intent and answers with safety-plan snippets + hotlines.                           |
| **Retrieval-Augmented Generation (RAG)** | Utilizes multiple RAG namespaces: `theory`, `personal_plan`, `session_data`, `future_me`.            |
| **Modern LangChain Chains**              | Employs `create_retrieval_chain` and `create_stuff_documents_chain` for efficient RAG.                 |
| **Singleton RagOrchestrator**            | Instantiated once at startup for efficient RAG queries related to session summarization.             |
| **Therapist Co-creation**                | Clinician and client build a *Future-Me Narrative* (stored in `future_me` RAG namespace).            |
| **Session Summarization**                | `/rag/session/{id}/summarize` endpoint (Note: document retrieval for summarization is a TODO).       |
| **Demo Mode & Auth Mode**                | Supports public chat in demo mode and JWT-protected chat in production mode.                         |

---

## 🏗️ Architecture & Flow

### Runtime Flow

```mermaid
flowchart TD

  %% ── Top: Onboarding ───────────────────────────────────────
  subgraph Onboarding["Therapist Onboarding"]
    direction TB
    OA["Therapist uploads docs (e.g., personal plan, session notes, future-me profile)"]
    OB["Docs indexed into respective RAG namespaces (ChromaDB)"]
    OA --> OB
  end

  %% ── Middle: Client Chat Loop ─────────────────────────────
  subgraph ChatLoop["Client Chat Loop via /chat/text"]
    direction TB
    CLIENT_MSG["Client sends message"]
    ORCH["Orchestrator receives message"]
    DETECT_RISK{"Orchestrator: Detect self-harm keywords?"}
    
    subgraph CrisisPath [Crisis Response]
        LOG_ALERT_CRISIS["Log warning & (conceptually) alert therapist"]
        CRISIS_CHAIN["Invoke Crisis Chain (RetrievalQA on 'personal_plan' namespace)"]
        CRISPLY["Respond with crisis resources (from safety plan & hotline info)"]
    end

    subgraph RagPath [Standard RAG Response]
        COMBINED_RETRIEVER["Invoke CombinedRetriever (searches 'theory', 'plan', 'session', 'future_me' namespaces)"]
        QUESTION_ANSWER_CHAIN["Invoke Question/Answer Chain (create_stuff_documents_chain with 'system_prompt.md')"]
        RAG_REPLY["System reply (persona-based, empathetic, ≤ 100 words, 1 action)"]
    end

    CLIENT_MSG --> ORCH
    ORCH --> DETECT_RISK
    DETECT_RISK -- Yes --> LOG_ALERT_CRISIS --> CRISIS_CHAIN --> CRISPLY
    DETECT_RISK -- No  --> COMBINED_RETRIEVER --> QUESTION_ANSWER_CHAIN --> RAG_REPLY
    
    CRISPLY --> CLIENT_MSG_LOOP_END[Client Receives Reply]
    RAG_REPLY --> CLIENT_MSG_LOOP_END
  end

  %% ── Bottom: Therapist Review ─────────────────────────────
  subgraph Review["Therapist Review (Conceptual)"]
    direction TB
    RA["Therapist calls /rag/session/{id}/summarize (TODO: full implementation)"]
    RB["Therapist reviews summary & potentially updates client documents"]
    RA --> RB
  end

  %% ── Cross-stage links ────────────────────────────────────
  OB -- RAG data available for --> ChatLoop
  CLIENT_MSG_LOOP_END -- (Session data might be logged/ingested) --> RA
  RB -- Updates docs for --> OB
```

---

## 🚀 Quickstart

### Prerequisites

*   Docker
*   Docker Compose (Recommended for running with ChromaDB)
*   Python 3.11+ (for local development without Docker)
*   A valid OpenAI API key.

### Setup `.env`

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-org/dear_future_me.git # Replace with your repo URL
    cd dear_future_me
    ```
2.  Copy the example environment file and configure it:
    ```bash
    cp .env.example .env
    ```
3.  Edit `.env` to set your `SECRET_KEY`, `DATABASE_URL` (if not using the default SQLite), and especially your `OPENAI_API_KEY`.
    *   To generate a `SECRET_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### Option 1: Running with Docker Compose (Recommended)

This starts the FastAPI application and a ChromaDB vector store.

```bash
docker-compose up --build -d
```

### Option 2: Running Locally (without Docker for ChromaDB)

This is suitable if you want to run ChromaDB separately or use an in-memory version for quick tests (requires code changes in `DocumentProcessor` for non-persistent Chroma). The default setup persists Chroma data to `./chroma_data`.

1.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt # For linters, testing tools
    ```
3.  Run database migrations (if `DEMO_MODE=false`):
    ```bash
    alembic upgrade head
    ```
4.  Start the FastAPI server:
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

### Verify Server is Running

```bash
curl http://localhost:8000/ping
# Expected output: {"ping":"pong"}
```

Access the API docs (Swagger UI) at http://localhost:8000/docs.

---

## 🗣️ Quickstart with CLI (Interacting with the Server)

The `app/cli.py` provides an interactive command-line interface to chat with the running API server.

1.  **Ensure the server is running** (either via Docker Compose or locally).
2.  **Open a new terminal** in the project root.
3.  **(If not using Docker for the CLI)** Activate your virtual environment: `source .venv/bin/activate`
4.  **Start the interactive chat**:
    ```bash
    python app/cli.py chat
    ```
    You can also specify the server URL if it's not running on the default `http://localhost:8000`:
    ```bash
    python app/cli.py chat --url http://your-server-address:port
    ```

*   If the server is running with `DEMO_MODE=false` (production mode), the CLI will automatically attempt to register a new temporary demo user and log in for the session.
*   If `DEMO_MODE=true`, authentication is bypassed for the chat endpoint.

---

## 🎭 Demo Mode vs. Production Mode

Controlled by the `DEMO_MODE` variable in your `.env` file.

*   **`DEMO_MODE=true`**:
    *   The `/chat/text` endpoint is public (no authentication required).
    *   The database is reset (tables dropped and recreated) on each application startup. Good for clean demos.
*   **`DEMO_MODE=false`** (Production-like):
    *   The `/chat/text` endpoint requires JWT authentication. Users must register and log in.
    *   Database migrations are applied on startup, but data persists.

---

## 💾 Managing the RAG Store (ChromaDB)

All vector data is persisted under the directory defined by `CHROMA_DIR` in `app.core.settings.py` (defaults to `./chroma_data` when running locally, or `/data` inside the `web` Docker container, mapped to the `chroma_data` volume).

### Ingesting Demo Data

Sample text files are provided in the `demo_data/` folder. Use the `demo_ingestion.sh` script to ingest them (ensure `CHROMA_DIR` in the script matches your setup if not using Docker Compose defaults):

```bash
./demo_ingestion.sh
```
This script first clears old demo collections from the specified `CHROMA_DIR` and then uses `curl` to call the `/rag/ingest/` endpoint for each demo file.

### Cleaning the RAG Store

*   **To reset all demo data if using `demo_ingestion.sh`**: Simply re-run `./demo_ingestion.sh`.
*   **Manual Cleaning (Local `CHROMA_DIR`)**:
    ```bash
    rm -rf ./chroma_data/*  # Or your configured CHROMA_DIR
    ```
*   **Manual Cleaning (Docker Volume)**: If using the `chroma_data` Docker volume:
    ```bash
    docker-compose down -v # This will stop containers and remove volumes, including chroma_data
    docker-compose up --build -d # Restart (Chroma will start with an empty store)
    # Then re-ingest data
    ```

---

## 🧪 Testing

Ensure you have development dependencies installed (`pip install -r requirements-dev.txt`).

```bash
# Run pytest suite (uses test.db, DEMO_MODE=true by default for tests)
pytest -q
```

---

## 📦 Project Structure (Simplified)

```text
├── app/                # FastAPI application
│   ├── api/            # API endpoint definitions (chat.py, orchestrator.py, rag.py)
│   ├── auth/           # Authentication logic
│   ├── core/           # Core settings and configurations
│   ├── db/             # Database session, models, migrations
+   │   ├── migrations/   # Alembic migration scripts
│   ├── rag/            # RAG processing logic (DocumentProcessor)
│   └── cli.py          # Interactive CLI client
│   └── main.py         # FastAPI app instantiation and main router setup
├── demo_data/          # Sample texts for RAG ingestion
├── templates/          # Prompt templates (system_prompt.md, crisis_prompt.md)
├── tests/              # Pytest suite
├── .env.example        # Example environment file
├── alembic.ini         # Alembic configuration
├── docker-compose.yml  # Docker Compose setup
├── Dockerfile          # Docker build instructions for the app
├── requirements.txt    # Main application dependencies
├── README.md           # This file
```

---

## 🙌 Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the Branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📜 License

MIT © Dear Future Me Team (or your chosen license and holder)

