# Dear Future Me – Runtime Flow

```mermaid
flowchart TD

  %% ── Top: Onboarding ───────────────────────────────────────
  subgraph Onboarding["Therapist Onboarding"]
    direction TB
    OA["Therapist uploads docs"]
    OB["Index into RAG store: theory, plan, session"]
    OA --> OB
  end

  %% ── Middle: Client Chat Loop ─────────────────────────────
  subgraph ChatLoop["Client Chat Loop"]
    direction TB
    CA["Client message"]
    CB{"Contains self-harm keywords?"}
    CC["Log warning & alert therapist"]
    CD["Respond with crisis resources"]
    CE["Retrieve & RAG QA"]
    CF["System reply (≤ 100 words, 1 action)"]
    FMP["Future Me Profile (persona prompt)"]

    CA --> CB
    CB -- Yes --> CC --> CD --> CA
    CB -- No  --> CE --> CF --> CA
    FMP --> CE
  end

  %% ── Bottom: Therapist Review ─────────────────────────────
  subgraph Review["Therapist Review"]
    direction TB
    RA["Therapist calls /rag/session/{id}/summarize"]
    RB["Review summary & update docs"]
    RA --> RB
  end

  %% ── Cross-stage links ────────────────────────────────────
  OB --> CA
  CF --> RA
  RB --> OB
  RB --> OA
