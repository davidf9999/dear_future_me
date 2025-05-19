# DFM Data Management Strategy for Personalized LLM Interaction

DFM strategically manages user-specific data across relational database tables and Retrieval Augmented Generation (RAG) namespaces. This division optimizes data use by the Large Language Model (LLM), ensuring both immediate context for personalization and dynamic access to detailed information.

## 1. Relational Database Tables

These tables store structured, user-specific information critical for immediate personalization, guiding the LLM's behavior, and supporting safety protocols. The system prompt template will incorporate the content of these tables for the client user.

### `UserProfileTable`

Stores core user attributes and preferences.

```sql
CREATE TABLE UserProfileTable (
    user_id UUID PRIMARY KEY,                                  -- Foreign key to the main UserTable
    name VARCHAR(255),                                         -- User's preferred name
    future_me_persona_summary TEXT,                            -- Concise summary of the user's "future self" persona
    
    -- Therapeutic and Tone Alignment
    gender_identity_pronouns VARCHAR(100),                     -- User's gender identity and/or pronouns
    therapeutic_setting VARCHAR(255),                          -- E.g., 'private therapy', 'school-based therapy'
    therapy_start_date DATE,                                   -- Date when the user started their current therapy
    dfm_use_integration_status VARCHAR(50)                     -- E.g., 'independently', 'integrated_with_therapist'
        CHECK (dfm_use_integration_status IN ('independently', 'integrated_with_therapist')),
    primary_emotional_themes TEXT,                             -- Key emotional themes the user is working through (e.g., 'hopelessness', 'self-criticism')
    recent_triggers_events TEXT,                               -- Brief description of recent triggers or significant events
    emotion_regulation_strengths TEXT,                         -- User's identified strengths for emotion regulation (e.g., 'journaling', 'physical movement')
    identified_values TEXT,                                    -- User's core identified values (e.g., 'creativity, connection')
    self_reported_goals TEXT,                                  -- User's self-reported goals for using DFM or for therapy
    therapist_language_to_mirror TEXT,                         -- Specific phrases or language style suggested by a therapist to mirror
    user_emotional_tone_preference VARCHAR(100),               -- User's preferred emotional tone for DFM's "future self" messages
    tone_alignment VARCHAR(100),                               -- General desired tone for DFM interactions (e.g., 'soft and reflective', 'grounded and direct')

    -- Optional fields for clinical questionnaire summaries (use with care, primarily for tone/prompt adaptation)
    c_ssrs_status VARCHAR(255),                                -- Latest C-SSRS status (e.g., 'Moderate ideation, no plan'). Used for adapting grounding questions.
    bdi_ii_score INTEGER,                                      -- Latest BDI-II score. Used to inform prompts regarding hopelessness or cognitive distortions.
    inq_status VARCHAR(255),                                   -- Latest INQ status (e.g., 'High perceived burdensomeness, low belongingness'). Used to emphasize connectedness.

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES UserTable(id) ON DELETE CASCADE
);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profile_modtime
BEFORE UPDATE ON UserProfileTable
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
```

### `SafetyPlanTable`

Stores the user's structured safety plan, directly referenced during crisis protocols. This is a one-to-one extension of the `UserProfileTable`.

```sql
CREATE TABLE SafetyPlanTable (
    user_id UUID PRIMARY KEY,                                  -- Foreign key to the UserProfileTable and UserTable, ensuring one safety plan per user
    step_1_warning_signs TEXT,                                 -- User-specific warning signs of escalating distress
    step_2_internal_coping TEXT,                               -- User's internal coping strategies
    step_3_social_distractions TEXT,                           -- Social contacts or settings for distraction
    step_4_help_sources TEXT,                                  -- People the user can reach out to for help (friends, family, therapist)
    step_5_professional_resources TEXT,                        -- Professional help resources (hotlines, clinics)
    step_6_environment_risk_reduction TEXT,                    -- Steps to make the immediate environment safer

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES UserTable(id) ON DELETE CASCADE
);

-- Trigger to update updated_at timestamp
CREATE TRIGGER update_safety_plan_modtime
BEFORE UPDATE ON SafetyPlanTable
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
```

## 2. RAG (Retrieval Augmented Generation) Namespaces

These namespaces store larger bodies of text, detailed narratives, or general knowledge. Data is retrieved through semantic search, providing relevant contextual snippets to the LLM dynamically, without overwhelming its context window.

*   **`theory`**:
    *   Contains general theoretical information and foundational knowledge (e.g., therapy principles, psychological concepts) forming a base knowledge layer for the AI.
*   **`personal_plan`**:
    *   Stores details of a user's personal therapeutic plan, extensive goals, and strategies that are too detailed for the `UserProfileTable`. Used to tailor responses to their established strategies.
*   **`session_data`**:
    *   Holds full transcripts of previous DFM chat sessions, allowing the AI to maintain conversational context and refer to past interactions if needed.
*   **`future_me`**:
    *   Contains in-depth information about the user's "future self" persona, including detailed aspirations, values articulations, and strengths narratives that go beyond the concise summaries in `UserProfileTable`.
*   **`therapist_notes`**:
    *   Stores notes, observations, and guidance provided by a therapist or administrator regarding a specific user, allowing the AI to incorporate professional insights.
*   **`dfm_chat_history_summaries`**:
    *   Contains concise summaries of past DFM chat sessions, automatically generated by DFM. These allow the AI to quickly grasp the essence of previous interactions for efficient RAG, distinct from the raw `session_data`.