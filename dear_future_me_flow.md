```mermaid
flowchart LR
  %% ┌───────────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────────┐
  %% │  Therapist Onboarding     │    │  Client Chat Loop         │    │  Therapist Review         │
  %% └───────────────────────────┘    └───────────────────────────┘    └───────────────────────────┘

  %% Left column
  subgraph Onboarding["Therapist Onboarding"]
    A["Therapist uploads docs"]
    B["Index into Chroma\nnamespaces: theory, plan, session"]
    A --> B
  end

  %% Center column
  subgraph ChatLoop["Client Chat Loop"]
    C["Client message"]
    D{"Contains self-harm\nkeywords?"}
    E["Log warning\n& alert therapist"]
    F["Respond with\ncrisis resources"]
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

  %% Right column
  subgraph Review["Therapist Review"]
    I["Therapist calls\n/rag/session/{id}/summarize"]
    J["Review summary &\nupdate docs"]
    I --> J
  end

  %% Cross-column connections
  B --> C
  H --> I
  J --> B
