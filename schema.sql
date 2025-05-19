CREATE TABLE IF NOT EXISTS "UserTable" (
        first_name VARCHAR, 
        last_name VARCHAR, 
        id CHAR(36) NOT NULL, 
        email VARCHAR(320) NOT NULL, 
        hashed_password VARCHAR(1024) NOT NULL, 
        is_active BOOLEAN NOT NULL, 
        is_superuser BOOLEAN NOT NULL, 
        is_verified BOOLEAN NOT NULL, 
        PRIMARY KEY (id)
);
CREATE UNIQUE INDEX "ix_UserTable_email" ON "UserTable" (email);

sqlite> .schema UserProfileTable
CREATE TABLE IF NOT EXISTS "UserProfileTable" (
        user_id UUID NOT NULL, 
        name VARCHAR(255), 
        future_me_persona_summary TEXT, 
        gender_identity_pronouns VARCHAR(100), 
        therapeutic_setting VARCHAR(255), 
        therapy_start_date DATE, 
        dfm_use_integration_status VARCHAR(50), 
        primary_emotional_themes TEXT, 
        recent_triggers_events TEXT, 
        emotion_regulation_strengths TEXT, 
        identified_values TEXT, 
        self_reported_goals TEXT, 
        therapist_language_to_mirror TEXT, 
        user_emotional_tone_preference VARCHAR(100), 
        tone_alignment VARCHAR(100), 
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
        updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
        PRIMARY KEY (user_id), 
        FOREIGN KEY(user_id) REFERENCES "UserTable" (id) ON DELETE CASCADE
);
/*Missing: optional fields: 
- c_css_status
- bdi_ii_score
- inq_status
*/

sqlite> .schema SafetyPlanTable
CREATE TABLE IF NOT EXISTS "SafetyPlanTable" (
        user_id UUID NOT NULL, 
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
        updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
        step_1_warning_signs TEXT, 
        step_2_internal_coping TEXT, 
        step_3_social_distractions TEXT, 
        step_4_help_sources TEXT, 
        step_5_professional_resources TEXT, 
        step_6_environment_risk_reduction TEXT, 
        PRIMARY KEY (user_id), 
        FOREIGN KEY(user_id) REFERENCES "UserTable" (id) ON DELETE CASCADE
);