# Dear Future Me – Runtime Flow

```mermaid
%%{init: {
  "theme": "dark",
  "flowchart": { "curve": "linear" }
}}%%
flowchart TB

  subgraph Onboarding [Therapist Onboarding]
    A["Therapist uploads docs"]
    B["Index into Chroma\n(theory, plan, session)"]
    A --> B
  end

  subgraph ClientChat [Client Chat Loop]
    C["Client message"]
    D{"Contains self-harm\nkeywords?"}

    C --> D
    D -- Yes --> E["Log warning &\nalert therapist"]
    E --> F["Respond with\ncrisis resources"]
    F --> C

    D -- No --> G["Retrieve &\nRAG QA"]
    G --> H["System reply\n(≤100 words, 1 action)"]
    H --> C
  end

  subgraph TherapistReview [Therapist Review]
    H -.-> I["Therapist calls\n/rag/session/{id}/summarize"]
    I --> J["Review summary\n& update docs"]
    J --> B
  end
