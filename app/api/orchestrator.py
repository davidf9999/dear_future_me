# /home/dfront/code/dear_future_me/app/api/orchestrator.py
import logging
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import Request
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from app.auth import crud_profile
from app.auth.models import UserTable
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

    async def ainvoke(self, inputs: Dict[str, Any]) -> str:  # Chain now returns str
        query = inputs.get("query", "")
        user = inputs.get("user")

        # The crisis_chain and rag_chain both end with StrOutputParser,
        # so they will return strings.
        if self.risk_detector(query):
            # Pass only necessary inputs for crisis_chain's prompt template
            return await self.crisis_chain.ainvoke(
                {
                    "query": query,
                    "user": user,
                    # context is usually not needed for crisis if it's a direct response
                }
            )
        else:
            # Pass only necessary inputs for rag_chain's prompt template
            return await self.rag_chain.ainvoke(
                {
                    "input": query,  # RAG chain expects 'input'
                    "user": user,
                    # context will be fetched by the RAG chain itself
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
            # self.chain.ainvoke now directly returns the string reply
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

        # Ensure these default templates include all variables _get_user_data_for_prompt provides
        # if the .md files are not found.
        default_crisis_prompt_str = (
            "You are a crisis responder. User query: {query}\n"
            "User Profile: Name: {user_name}, Summary: {user_profile_summary}, Persona: {future_me_persona_summary}, Pronouns: {gender_identity_pronouns}.\n"
            "Safety Plan: {user_safety_plan_summary}."
            # Add all other keys from _get_user_data_for_prompt if they are expected here
        )
        default_system_prompt_str = (
            "Based on the following context: {context}\n\nUser Input: {input}\n\n"
            "User Profile: Name: {user_name}, Summary: {user_profile_summary}, Persona: {future_me_persona_summary}, Pronouns: {gender_identity_pronouns}, Therapeutic Setting: {therapeutic_setting}.\n"  # Added therapeutic_setting
            "Safety Plan: {user_safety_plan_summary}.\n"
            "Identified Values: {identified_values}.\n"
            "Tone Alignment: {tone_alignment}.\n"
            "Self-Reported Goals: {self_reported_goals}.\n"
            "Recent Triggers/Events: {recent_triggers_events}.\n"
            "Emotion Regulation Strengths: {emotion_regulation_strengths}.\n"
            "Primary Emotional Themes: {primary_emotional_themes}.\n"
            "Therapist Language to Mirror: {therapist_language_to_mirror}.\n"
            "User Emotional Tone Preference: {user_emotional_tone_preference}."
            # Add all other keys from _get_user_data_for_prompt
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

    async def _get_user_data_for_prompt(self, user: Optional[UserTable]) -> Dict[str, str]:
        user_data = {
            "user_name": "User",
            "user_profile_summary": "User profile not available.",
            "user_safety_plan_summary": "User safety plan not available.",
            "future_me_persona_summary": "Future persona summary not available.",
            "gender_identity_pronouns": "Pronouns not specified.",
            "user_pronouns": "Pronouns not specified.",
            "therapeutic_setting": "Setting not specified.",
            "identified_values": "Values not specified.",
            "tone_alignment": "Tone alignment not specified.",
            "self_reported_goals": "Goals not specified.",
            "recent_triggers_events": "Recent triggers/events not specified.",
            "emotion_regulation_strengths": "Emotion regulation strengths not specified.",
            "primary_emotional_themes": "Primary emotional themes not specified.",
            "therapist_language_to_mirror": "Therapist language to mirror not specified.",
            "user_emotional_tone_preference": "User emotional tone preference not specified.",
        }

        if user and user.id:
            try:
                async with get_async_session_context() as db:
                    profile = await crud_profile.get_user_profile(db, user_id=user.id)
                    if profile:
                        user_data["user_name"] = profile.name or "User"
                        profile_parts = []
                        if profile.name:
                            profile_parts.append(f"Name: {profile.name}.")
                        if profile.future_me_persona_summary:
                            profile_parts.append(f"Persona Summary: {profile.future_me_persona_summary}.")
                            user_data["future_me_persona_summary"] = profile.future_me_persona_summary

                        user_data["gender_identity_pronouns"] = (
                            getattr(profile, "gender_identity_pronouns", None) or user_data["gender_identity_pronouns"]
                        )
                        user_data["user_pronouns"] = (
                            getattr(profile, "gender_identity_pronouns", None) or user_data["user_pronouns"]
                        )
                        user_data["therapeutic_setting"] = (
                            getattr(profile, "therapeutic_setting", None) or user_data["therapeutic_setting"]
                        )
                        # Add other profile fields similarly using getattr for safety
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
                        user_data["emotion_regulation_strengths"] = (
                            getattr(profile, "emotion_regulation_strengths", None)
                            or user_data["emotion_regulation_strengths"]
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

                        if profile_parts:
                            user_data["user_profile_summary"] = " ".join(profile_parts)
                        else:
                            user_data["user_profile_summary"] = "User profile exists but has no summary details."

                    safety_plan = await safety_plan_crud.get_safety_plan_by_user_id(db, user_id=user.id)
                    if safety_plan:
                        plan_parts = []
                        if safety_plan.warning_signs:
                            plan_parts.append(f"Warning Signs: {safety_plan.warning_signs}.")
                        if safety_plan.coping_strategies:
                            plan_parts.append(f"Coping Strategies: {safety_plan.coping_strategies}.")
                        if plan_parts:
                            user_data["user_safety_plan_summary"] = " ".join(plan_parts)
                        else:
                            user_data["user_safety_plan_summary"] = (
                                "User safety plan exists but has no summary details."
                            )
            except Exception as e:
                logging.error(f"Error fetching user data for user {user.id}: {e}")

        return user_data

    def _build_crisis_chain(self) -> Runnable:
        async def prepare_crisis_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data_dict = await self._get_user_data_for_prompt(user)
            return {
                "query": input_dict.get("query", ""),
                # "context" is not typically used by a direct crisis response template
                # but include if your crisis_prompt_template_str uses {context}
                **user_data_dict,
            }

        return RunnableLambda(prepare_crisis_input) | self.crisis_prompt_template | self.llm | StrOutputParser()

    def _build_placeholder_rag_chain(self) -> Runnable:  # This is not used by RagOrchestrator instance
        async def prepare_rag_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data_dict = await self._get_user_data_for_prompt(user)
            return {
                "input": input_dict.get("input", ""),
                "context": "Placeholder context from base orchestrator.",  # Placeholder
                **user_data_dict,
            }

        return RunnableLambda(prepare_rag_input) | self.system_prompt_template | self.llm | StrOutputParser()


class RagOrchestrator(Orchestrator):
    def __init__(self):
        super().__init__()  # Calls _load_prompts, _load_risk_keywords, LLM init
        # DocumentProcessors are initialized
        self.theory_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THEORY)
        self.personal_plan_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_PERSONAL_PLAN)
        self.session_data_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_SESSION_DATA)
        self.future_me_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_FUTURE_ME)
        self.therapist_notes_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THERAPIST_NOTES)
        self.dfm_chat_history_summaries_db = DocumentProcessor(
            namespace=self.settings.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES
        )

        # Now, self.system_prompt_template and self.crisis_prompt_template are loaded
        # from the parent. We rebuild the chains using these.
        self._crisis_chain = self._build_crisis_chain()  # Rebuild with potentially loaded prompts
        self._rag_chain = self._build_actual_rag_chain()
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"
        )
        self.summarize_chain: Runnable = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        # For now, just use one retriever.
        # TODO: Implement EnsembleRetriever or similar for multiple sources if needed.
        logging.info("_get_combined_retriever is using future_me_db as a placeholder for combined retrieval.")
        return self.future_me_db.vectordb.as_retriever(
            search_kwargs={"k": 3}  # Example: retrieve top 3
        )

    def _build_actual_rag_chain(self) -> Runnable:
        retriever = self._get_combined_retriever()

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        async def prepare_rag_input_with_retrieval_and_user_data(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            query = input_dict.get("input", "")  # RAG chain uses 'input'
            user = input_dict.get("user")

            retrieved_docs = await retriever.ainvoke(query)
            formatted_docs = format_docs(retrieved_docs)

            user_data_dict = await self._get_user_data_for_prompt(user)

            # This dictionary must match all variables in self.system_prompt_template
            return {"input": query, "context": formatted_docs, **user_data_dict}

        return (
            RunnableLambda(prepare_rag_input_with_retrieval_and_user_data)
            | self.system_prompt_template  # Uses the template loaded in Orchestrator.__init__
            | self.llm
            | StrOutputParser()
        )

    async def summarize_session(self, session_id: str) -> str:
        logging.info(f"Attempting to summarize session data for: {session_id}")
        text_to_summarize = (
            f"Placeholder data for session {session_id}. User discussed future goals and coping strategies."
        )

        try:
            response = await self.summarize_chain.ainvoke({"input": text_to_summarize})
            summary = response
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error summarizing session {session_id}: {e}")
            return f"Summary for {session_id} (unavailable due to error)"

    async def _summarize_docs_with_chain(self, docs: List[Document]) -> str:
        if not docs:
            return "No documents provided for summarization."
        combined_text = "\n\n".join([doc.page_content for doc in docs])
        logging.info(f"Summarizing combined text of {len(docs)} documents.")
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
