```mermaid
flowchart LR

  %% ── Left: Onboarding ───────────────────────────────────────
  subgraph Onboarding["Therapist Onboarding"]
    direction TB
    A["Therapist uploads docs"]
    B["Index into Chroma: theory, plan, session"]
    A --> B
  end

  %% ── Center: Client Chat Loop ───────────────────────────────
  subgraph ChatLoop["Client Chat Loop"]
    direction TB
    C["Client message"]
    D{"Contains self-harm keywords?"}
    E["Log warning & alert therapist"]
    F["Respond with crisis resources"]
    G["Retrieve & RAG QA"]
    H["System reply (<= 100 words, 1 action)"]

    C --> D
    D -- Yes --> E --> F --> C
    D -- No  --> G --> H --> C
  end

  %% ── Right: Therapist Review ────────────────────────────────
  subgraph Review["Therapist Review"]
    direction TB
    I["Therapist calls /rag/session/{id}/summarize"]
    J["Review summary & update docs"]
    I --> J
  end

  %% ── Cross-column flows ──────────────────────────────────────
  B --> C
  H --> I
  J --> B
  J -.-> A      %% dotted loop back to onboarding
