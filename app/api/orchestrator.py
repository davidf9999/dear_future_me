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

    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")
        user = inputs.get("user")

        if self.risk_detector(query):
            return await self.crisis_chain.ainvoke({"query": query, "context": [], "user": user})
        else:
            return await self.rag_chain.ainvoke({"input": query, "context": [], "user": user})


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
            result = await self.chain.ainvoke({"query": message, "input": message, "user": user})
            reply_content = result.get("answer") or result.get("result", "No specific reply found.")
            return {"reply": cast(str, reply_content)}
        except RuntimeError as e:
            logging.error(f"Error during chain invocation: {e}")
            return {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}
        except Exception as e:
            logging.exception(f"Unexpected error in Orchestrator.answer: {e}")
            return {"reply": "An unexpected error occurred. Please try again."}

    def _load_prompts(self) -> None:
        # Simplified to only load generic English prompts
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(base_dir, self.settings.PROMPT_TEMPLATE_DIR)

        default_crisis_prompt_str = "You are a crisis responder."
        default_system_prompt_str = "Based on the following context:"

        crisis_prompt_file_generic = self.settings.CRISIS_PROMPT_FILE
        system_prompt_file_generic = self.settings.SYSTEM_PROMPT_FILE

        # Load crisis prompt
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

        # Load system prompt
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
        # Simplified to only load English keywords
        self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]

    def _detect_risk(self, query: str) -> bool:
        if not query:
            return False
        return any(keyword in query.lower() for keyword in self._risk_keywords)

    async def _get_user_data_for_prompt(self, user: Optional[UserTable]) -> Dict[str, str]:
        profile_summary = "User profile not available."
        safety_plan_summary = "User safety plan not available."
        if user:
            async with get_async_session_context() as db:
                profile = await crud_profile.get_user_profile(db, user_id=user.id)
                if profile:
                    profile_summary = (
                        f"Name: {profile.name or 'N/A'}. Persona Summary: {profile.future_me_persona_summary or 'N/A'}."
                    )

                safety_plan = await safety_plan_crud.get_safety_plan_by_user_id(db, user_id=user.id)
                if safety_plan:
                    safety_plan_summary = (
                        f"Warning Signs: {safety_plan.warning_signs or 'N/A'}. "
                        f"Coping Strategies: {safety_plan.coping_strategies or 'N/A'}."
                    )
        return {
            "user_profile_summary": profile_summary,
            "user_safety_plan_summary": safety_plan_summary,
        }

    def _build_crisis_chain(self) -> Runnable:
        async def prepare_crisis_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data = await self._get_user_data_for_prompt(user)
            return {
                "query": input_dict.get("query", ""),
                "context": input_dict.get("context", []),
                "user_profile_summary": user_data["user_profile_summary"],
                "user_safety_plan_summary": user_data["user_safety_plan_summary"],
            }

        return RunnableLambda(prepare_crisis_input) | self.crisis_prompt_template | self.llm | StrOutputParser()

    def _build_placeholder_rag_chain(self) -> Runnable:
        async def prepare_rag_input(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            user = input_dict.get("user")
            user_data = await self._get_user_data_for_prompt(user)
            return {
                "input": input_dict.get("input", ""),
                "context": "Placeholder context from base orchestrator.",
                "user_profile_summary": user_data["user_profile_summary"],
                "user_safety_plan_summary": user_data["user_safety_plan_summary"],
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

        self._rag_chain = self._build_actual_rag_chain()
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"
        )
        self.summarize_chain: Runnable = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        logging.warning(
            "_get_combined_retriever is using future_me_db as a placeholder for combined retrieval. "
            "Implement proper multi-namespace retrieval."
        )
        return self.future_me_db.vectordb.as_retriever()

    def _build_actual_rag_chain(self) -> Runnable:
        retriever = self._get_combined_retriever()

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        async def prepare_rag_input_with_retrieval_and_user_data(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            query = input_dict.get("input", "")
            user = input_dict.get("user")

            retrieved_docs = await retriever.ainvoke(query)
            formatted_docs = format_docs(retrieved_docs)

            user_data = await self._get_user_data_for_prompt(user)

            return {
                "input": query,
                "context": formatted_docs,
                "user_profile_summary": user_data["user_profile_summary"],
                "user_safety_plan_summary": user_data["user_safety_plan_summary"],
            }

        return (
            RunnableLambda(prepare_rag_input_with_retrieval_and_user_data)
            | self.system_prompt_template
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
