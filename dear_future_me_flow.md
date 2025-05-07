```mermaid
flowchart LR
  %% ┌─────────────────────────────────────────────┐
  %% │  Therapist Onboarding                      │
  %% └─────────────────────────────────────────────┘
  subgraph Onboarding
    A["Therapist uploads docs"]
    B["Index into Chroma\nnamespaces: theory, plan, session"]
  end

  %% ┌─────────────────────────────────────────────┐
  %% │  Client Chat Loop                          │
  %% └─────────────────────────────────────────────┘
  subgraph ChatLoop
    C["Client message"]
    D{"Contains self-harm\nkeywords?"}
    E["Log warning & alert therapist"]
    F["Respond with crisis resources"]
    G["Retrieve & RAG QA"]
    H["System reply\n(≤100 words, 1 action)"]

    C --> D
    D -- Yes --> E
    E --> F
    F --> C

    D -- No --> G
    G --> H
    H --> C
  end

  %% ┌─────────────────────────────────────────────┐
  %% │  Therapist Review                          │
  %% └─────────────────────────────────────────────┘
  subgraph Review
    I["Therapist calls\n/rag/session/{id}/summarize"]
    J["Review summary &\nupdate docs"]
  end

  %% ↘ Onboarding → Chat
  B --> C

  %% ↘ Chat → Review
  H --> I

  %% ↘ Review → Onboarding
  J --> B
