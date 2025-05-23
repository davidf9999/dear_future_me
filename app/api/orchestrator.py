# /home/dfront/code/dear_future_me/app/api/orchestrator.py
# Full file content
import logging
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import Request
from langchain.prompts import ChatPromptTemplate
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from app.auth import crud_profile
from app.auth.models import SafetyPlanTable, UserTable
from app.core.settings import get_settings
from app.db.session import get_async_session_context
from app.rag.processor import DocumentProcessor
from app.safety_plan import crud as safety_plan_crud

cfg = get_settings()


class BranchingChain:
    def __init__(self, risk_detector, crisis_chain, rag_chain):
        self.risk_detector = risk_detector
        self.crisis_chain = crisis_chain
        self.rag_chain = rag_chain

    async def ainvoke(self, inputs: Dict[str, Any]) -> str:
        query = inputs.get("query", "")
        user = inputs.get("user")

        if self.risk_detector(query):
            return await self.crisis_chain.ainvoke(
                {
                    "query": query,
                    "user": user,
                }
            )
        else:
            return await self.rag_chain.ainvoke(
                {
                    "input": query,
                    "user": user,
                }
            )


class Orchestrator:
    def __init__(self):
        self.settings = cfg
        self._load_prompts()
        self._load_risk_keywords()

        self.llm = ChatOpenAI(
            model=self.settings.LLM_MODEL,
            temperature=self.settings.LLM_TEMPERATURE,
            api_key=self.settings.OPENAI_API_KEY,
        )
        self._crisis_chain = self._build_crisis_chain()
        self._rag_chain = self._build_placeholder_rag_chain()
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

    async def answer(self, message: str, user: Optional[UserTable] = None) -> Dict[str, Any]:
        try:
            reply_content = await self.chain.ainvoke({"query": message, "input": message, "user": user})
            return {"reply": reply_content}
        except KeyError as e:
            logging.error(
                f"KeyError during prompt formatting: {e}. This means a variable is missing for the prompt template."
            )
            return {
                "reply": "I’m sorry, there was an issue preparing my response due to missing information. Please contact support."
            }
        except RuntimeError as e:
            logging.error(f"Error during chain invocation: {e}")
            return {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}
        except Exception as e:
            logging.exception(f"Unexpected error in Orchestrator.answer: {e}")
            return {"reply": "An unexpected error occurred. Please try again."}

    def _load_prompts(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(base_dir, self.settings.PROMPT_TEMPLATE_DIR)

        default_crisis_prompt_str = (
            "You are a crisis responder. User query: {query}\n"
            "User Profile: Name: {name}, Pronouns: {gender_identity_pronouns}, Strengths: {emotion_regulation_strengths}.\n"
            "Safety Plan Details:\n"
            "Warning Signs: {step_1_warning_signs}\n"
            "Internal Coping Strategies: {step_2_internal_coping}\n"
            "Social Distractions: {step_3_social_distractions}\n"
            "Help Sources: {step_4_help_sources}\n"
            "Professional Resources: {step_5_professional_resources}\n"
            "Environment Risk Reduction: {step_6_environment_risk_reduction}"
        )
        default_system_prompt_str = (
            "Based on the following context: {context}\n\nUser Input: {input}\n\n"
            "User Profile:\nName: {name}\nSummary: {user_profile_summary}\nPersona: {future_me_persona_summary}\nPronouns: {gender_identity_pronouns}\nTherapeutic Setting: {therapeutic_setting}.\n"
            "Therapy Start Date: {therapy_start_date}.\nDFM Use Integration Status: {dfm_use_integration_status}.\n"  # Added
            "C-SSRS Status: {c_ssrs_status}.\nBDI-II Score: {bdi_ii_score}.\nINQ Status: {inq_status}.\n"  # Added
            "Safety Plan Summary: {user_safety_plan_summary}.\n"
            "Identified Values: {identified_values}.\n"
            "Tone Alignment: {tone_alignment}.\n"
            "Self-Reported Goals: {self_reported_goals}.\n"
            "Recent Triggers/Events: {recent_triggers_events}.\n"
            "Emotion Regulation Strengths: {emotion_regulation_strengths}.\n"
            "Primary Emotional Themes: {primary_emotional_themes}.\n"
            "Therapist Language to Mirror: {therapist_language_to_mirror}.\n"
            "User Emotional Tone Preference: {user_emotional_tone_preference}."
        )

        crisis_prompt_file_generic = self.settings.CRISIS_PROMPT_FILE
        system_prompt_file_generic = self.settings.SYSTEM_PROMPT_FILE

        try:
            path_to_try = os.path.join(template_dir, crisis_prompt_file_generic)
            if os.path.exists(path_to_try):
                with open(path_to_try, "r", encoding="utf-8") as f:
                    self.crisis_prompt_template_str = f.read()
            else:
                self.crisis_prompt_template_str = default_crisis_prompt_str
                logging.warning(
                    f"Generic crisis prompt ('{crisis_prompt_file_generic}') not found. Using hardcoded default."
                )
        except Exception as e:
            logging.error(f"Error loading crisis prompt: {e}")
            self.crisis_prompt_template_str = default_crisis_prompt_str

        try:
            path_to_try = os.path.join(template_dir, system_prompt_file_generic)
            if os.path.exists(path_to_try):
                with open(path_to_try, "r", encoding="utf-8") as f:
                    self.system_prompt_template_str = f.read()
            else:
                self.system_prompt_template_str = default_system_prompt_str
                logging.warning(
                    f"Generic system prompt ('{system_prompt_file_generic}') not found. Using hardcoded default."
                )
        except Exception as e:
            logging.error(f"Error loading system prompt: {e}")
            self.system_prompt_template_str = default_system_prompt_str

        self.crisis_prompt_template = ChatPromptTemplate.from_template(self.crisis_prompt_template_str)
        self.system_prompt_template = ChatPromptTemplate.from_template(self.system_prompt_template_str)

    def _load_risk_keywords(self) -> None:
        self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]

    def _detect_risk(self, query: str) -> bool:
        if not query:
            return False
        return any(keyword in query.lower() for keyword in self._risk_keywords)

    async def _get_user_data_for_prompt(self, user: Optional[UserTable]) -> Dict[str, Any]:
        user_data: Dict[str, Any] = {
            "name": "User",
            "user_profile_summary": "User profile not available.",
            "future_me_persona_summary": "Future persona summary not available.",
            "gender_identity_pronouns": "Pronouns not specified.",
            "emotion_regulation_strengths": "Strengths not specified.",
            "therapeutic_setting": "Setting not specified.",
            "identified_values": "Values not specified.",
            "tone_alignment": "Tone alignment not specified.",
            "self_reported_goals": "Goals not specified.",
            "recent_triggers_events": "Recent triggers/events not specified.",
            "primary_emotional_themes": "Primary emotional themes not specified.",
            "therapist_language_to_mirror": "Therapist language to mirror not specified.",
            "user_emotional_tone_preference": "User emotional tone preference not specified.",
            "user_safety_plan_summary": "User safety plan summary not available.",
            # New fields with defaults
            "therapy_start_date": "Not available.",
            "dfm_use_integration_status": "Not available.",
            "c_ssrs_status": "Not available.",
            "bdi_ii_score": "Not available.",
            "inq_status": "Not available.",
            # Placeholders for individual safety plan steps
            "step_1_warning_signs": "Not specified.",
            "step_2_internal_coping": "Not specified.",
            "step_3_social_distractions": "Not specified.",
            "step_4_help_sources": "Not specified.",
            "step_5_professional_resources": "Not specified.",
            "step_6_environment_risk_reduction": "Not specified.",
            "raw_safety_plan": None,
        }

        if user and user.id:
            try:
                async with get_async_session_context() as db:
                    profile = await crud_profile.get_user_profile(db, user_id=user.id)
                    if profile:
                        profile_parts = []
                        if profile.name:
                            profile_parts.append(f"Name: {profile.name}.")
                        if profile.future_me_persona_summary:
                            profile_parts.append(f"Persona Summary: {profile.future_me_persona_summary}.")
                            user_data["future_me_persona_summary"] = profile.future_me_persona_summary

                        user_data["name"] = getattr(profile, "name", None) or user_data["name"]
                        user_data["gender_identity_pronouns"] = (
                            getattr(profile, "gender_identity_pronouns", None) or user_data["gender_identity_pronouns"]
                        )
                        user_data["emotion_regulation_strengths"] = (
                            getattr(profile, "emotion_regulation_strengths", None)
                            or user_data["emotion_regulation_strengths"]
                        )
                        user_data["therapeutic_setting"] = (
                            getattr(profile, "therapeutic_setting", None) or user_data["therapeutic_setting"]
                        )
                        user_data["identified_values"] = (
                            getattr(profile, "identified_values", None) or user_data["identified_values"]
                        )
                        user_data["tone_alignment"] = (
                            getattr(profile, "tone_alignment", None) or user_data["tone_alignment"]
                        )
                        user_data["self_reported_goals"] = (
                            getattr(profile, "self_reported_goals", None) or user_data["self_reported_goals"]
                        )
                        user_data["recent_triggers_events"] = (
                            getattr(profile, "recent_triggers_events", None) or user_data["recent_triggers_events"]
                        )
                        user_data["primary_emotional_themes"] = (
                            getattr(profile, "primary_emotional_themes", None) or user_data["primary_emotional_themes"]
                        )
                        user_data["therapist_language_to_mirror"] = (
                            getattr(profile, "therapist_language_to_mirror", None)
                            or user_data["therapist_language_to_mirror"]
                        )
                        user_data["user_emotional_tone_preference"] = (
                            getattr(profile, "user_emotional_tone_preference", None)
                            or user_data["user_emotional_tone_preference"]
                        )
                        # Populate new fields
                        user_data["therapy_start_date"] = (
                            str(profile.therapy_start_date)
                            if profile.therapy_start_date
                            else user_data["therapy_start_date"]
                        )
                        user_data["dfm_use_integration_status"] = (
                            profile.dfm_use_integration_status or user_data["dfm_use_integration_status"]
                        )
                        user_data["c_ssrs_status"] = profile.c_ssrs_status or user_data["c_ssrs_status"]
                        user_data["bdi_ii_score"] = profile.bdi_ii_score or user_data["bdi_ii_score"]
                        user_data["inq_status"] = profile.inq_status or user_data["inq_status"]

                        if profile_parts:
                            user_data["user_profile_summary"] = " ".join(profile_parts)
                        else:
                            user_data["user_profile_summary"] = "User profile exists but has no summary details."

                    safety_plan: Optional[SafetyPlanTable] = await safety_plan_crud.get_safety_plan_by_user_id(
                        db, user_id=user.id
                    )
                    user_data["raw_safety_plan"] = safety_plan

                    if safety_plan:
                        summary_parts = []
                        if safety_plan.step_1_warning_signs:
                            summary_parts.append(f"Warning Signs: {safety_plan.step_1_warning_signs}.")
                        if safety_plan.step_2_internal_coping:
                            summary_parts.append(f"Internal Coping Strategies: {safety_plan.step_2_internal_coping}.")
                        if summary_parts:
                            user_data["user_safety_plan_summary"] = " ".join(summary_parts)
                        else:
                            user_data["user_safety_plan_summary"] = (
                                "User safety plan exists but has no summary details."
                            )

                        # Populate individual step fields for the crisis prompt
                        user_data["step_1_warning_signs"] = safety_plan.step_1_warning_signs or "Not specified."
                        user_data["step_2_internal_coping"] = safety_plan.step_2_internal_coping or "Not specified."
                        user_data["step_3_social_distractions"] = (
                            safety_plan.step_3_social_distractions or "Not specified."
                        )
                        user_data["step_4_help_sources"] = safety_plan.step_4_help_sources or "Not specified."
                        user_data["step_5_professional_resources"] = (
                            safety_plan.step_5_professional_resources or "Not specified."
                        )
                        user_data["step_6_environment_risk_reduction"] = (
                            safety_plan.step_6_environment_risk_reduction or "Not specified."
                        )
            except Exception as e:
                logging.error(f"Error fetching user data for user {user.id}: {e}")
        return user_data

    def _build_crisis_chain(self) -> Runnable:
        async def prepare_crisis_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data_dict = await self._get_user_data_for_prompt(user)

            return_dict = {
                "query": input_dict.get("query", ""),
                "name": user_data_dict.get("name", "User"),
                "gender_identity_pronouns": user_data_dict.get("gender_identity_pronouns", "not specified"),
                "emotion_regulation_strengths": user_data_dict.get(
                    "emotion_regulation_strengths", "Strengths not specified."
                ),
                "step_1_warning_signs": user_data_dict.get("step_1_warning_signs"),
                "step_2_internal_coping": user_data_dict.get("step_2_internal_coping"),
                "step_3_social_distractions": user_data_dict.get("step_3_social_distractions"),
                "step_4_help_sources": user_data_dict.get("step_4_help_sources"),
                "step_5_professional_resources": user_data_dict.get("step_5_professional_resources"),
                "step_6_environment_risk_reduction": user_data_dict.get("step_6_environment_risk_reduction"),
            }
            return return_dict

        return RunnableLambda(prepare_crisis_input) | self.crisis_prompt_template | self.llm | StrOutputParser()

    def _build_placeholder_rag_chain(self) -> Runnable:
        async def prepare_rag_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data_dict = await self._get_user_data_for_prompt(user)
            return {
                "input": input_dict.get("input", ""),
                "context": "Placeholder context from base orchestrator.",
                **user_data_dict,
            }

        return RunnableLambda(prepare_rag_input) | self.system_prompt_template | self.llm | StrOutputParser()


class RagOrchestrator(Orchestrator):
    def __init__(self):
        super().__init__()
        self.theory_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THEORY)
        self.personal_plan_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_PERSONAL_PLAN)
        self.session_data_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_SESSION_DATA)
        self.future_me_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_FUTURE_ME)
        self.therapist_notes_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THERAPIST_NOTES)
        self.dfm_chat_history_summaries_db = DocumentProcessor(
            namespace=self.settings.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES
        )

        self._crisis_chain = self._build_crisis_chain()
        self._rag_chain = self._build_actual_rag_chain()
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"
        )
        self.summarize_chain: Runnable = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        logging.info("Initializing combined retriever with EnsembleRetriever for multiple namespaces.")

        retriever_k = 2

        all_dbs = [
            self.theory_db,
            self.personal_plan_db,
            self.session_data_db,
            self.future_me_db,
            self.therapist_notes_db,
            self.dfm_chat_history_summaries_db,
        ]

        retrievers_list = [db.vectordb.as_retriever(search_kwargs={"k": retriever_k}) for db in all_dbs]

        ensemble_retriever = EnsembleRetriever(retrievers=retrievers_list)
        return ensemble_retriever

    def _build_actual_rag_chain(self) -> Runnable:
        retriever = self._get_combined_retriever()

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        async def prepare_rag_input_with_retrieval_and_user_data(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            query = input_dict.get("input", "")
            user = input_dict.get("user")
            retrieved_docs = await retriever.ainvoke(query)
            formatted_docs = format_docs(retrieved_docs)
            user_data_dict = await self._get_user_data_for_prompt(user)

            final_rag_input = {
                "input": query,
                "context": formatted_docs,
                **user_data_dict,
            }
            return final_rag_input

        return (
            RunnableLambda(prepare_rag_input_with_retrieval_and_user_data)
            | self.system_prompt_template
            | self.llm
            | StrOutputParser()
        )

    async def summarize_session(self, session_id: str) -> str:
        logging.info(f"Attempting to summarize session data for session_id: '{session_id}'")

        try:
            session_docs: List[Document] = self.session_data_db.query(
                query=f"session {session_id}",
                k=50,
                metadata_filter={"session_id": session_id},
            )
        except Exception as e:
            logging.error(f"Error querying session_data_db for session {session_id}: {e}")
            return f"Summary for session {session_id} (unavailable due to data retrieval error)"

        if not session_docs:
            logging.warning(
                f"No documents found for session_id: '{session_id}' in '{self.settings.CHROMA_NAMESPACE_SESSION_DATA}'. Cannot summarize."
            )
            return f"No data found to summarize for session {session_id}."

        summary = await self._summarize_docs_with_chain(session_docs)
        return summary

    async def _summarize_docs_with_chain(self, docs: List[Document]) -> str:
        if not docs:
            return "No documents provided for summarization."
        combined_text = "\n\n".join([doc.page_content for doc in docs])

        snippet_length = 500
        text_snippet = combined_text[:snippet_length] + "..." if len(combined_text) > snippet_length else combined_text
        logging.info(
            f"Summarizing combined text of {len(docs)} documents (length: {len(combined_text)} chars). Snippet: '{text_snippet}'"
        )

        try:
            response = await self.summarize_chain.ainvoke({"input": combined_text})
            summary = response
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error in _summarize_docs_with_chain: {e}")
            return "Could not generate summary due to an internal error."


async def get_orchestrator(request: Request) -> Orchestrator:
    if not hasattr(request.app.state, "rag_orchestrator_instance"):
        logging.info("RagOrchestrator not found in app.state, initializing now.")
        request.app.state.rag_orchestrator_instance = RagOrchestrator()
        logging.info("RagOrchestrator initialized and attached to app.state as rag_orchestrator_instance")
    return request.app.state.rag_orchestrator_instance
