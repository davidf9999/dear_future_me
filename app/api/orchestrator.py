# app/api/orchestrator.py
import logging
import os
import uuid  # Import uuid
from typing import Any, Dict, List, Optional, cast

from fastapi import Request
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.crud.user_profile import get_user_profile
from app.db.models import UserProfileTable
from app.rag.processor import DocumentProcessor

# Initialize settings once
cfg = get_settings()


async def get_user_prompt_components_from_db(user_id: str, db_session: AsyncSession) -> Optional[UserProfileTable]:
    """Fetches the user profile from the database."""
    logging.info(f"Fetching user profile for user_id: {user_id}")
    user_profile = await get_user_profile(db_session, user_id=uuid.UUID(user_id))
    if not user_profile:
        logging.warning(f"No profile found for user_id: {user_id}")
    return user_profile


class BranchingChain:
    def __init__(self, risk_detector, crisis_chain_builder, rag_chain_builder, llm):
        self.risk_detector = risk_detector
        self.crisis_chain_builder = crisis_chain_builder
        self.rag_chain_builder = rag_chain_builder
        self.llm = llm

    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")
        user_specific_system_prompt_template_str = inputs.get("user_system_prompt_str")
        user_specific_crisis_prompt_template_str = inputs.get("user_crisis_prompt_str")
        retriever = inputs.get("retriever")

        if not user_specific_system_prompt_template_str or not user_specific_crisis_prompt_template_str:
            logging.error("User-specific prompt strings not provided to BranchingChain")
            return {"reply_content": "Error: System configuration issue."}

        system_prompt = ChatPromptTemplate.from_template(user_specific_system_prompt_template_str)
        crisis_prompt = ChatPromptTemplate.from_template(user_specific_crisis_prompt_template_str)

        if self.risk_detector(query):
            crisis_chain = self.crisis_chain_builder(crisis_prompt, self.llm)
            return await crisis_chain.ainvoke({"query": query, "context": []})
        else:
            rag_chain = self.rag_chain_builder(system_prompt, self.llm, retriever)
            return await rag_chain.ainvoke({"input": query})


class Orchestrator:
    def __init__(self):
        self.settings = get_settings()
        self._load_base_prompt_templates()
        self._load_risk_keywords()

        self.llm = ChatOpenAI(
            model=self.settings.LLM_MODEL,
            temperature=self.settings.LLM_TEMPERATURE,
            api_key=self.settings.OPENAI_API_KEY,
        )
        self.chain = BranchingChain(self._detect_risk, self._build_crisis_chain, self._build_rag_chain, self.llm)

    async def get_user_specific_prompt_str(
        self, base_template_str: str, user_id: Optional[str], db_session: Optional[AsyncSession]
    ) -> str:
        """Fetches user profile and injects components into the base template."""
        if user_id and db_session:
            try:
                user_profile = await get_user_profile(db_session, user_id=uuid.UUID(user_id))
                populated_template = base_template_str

                placeholders = {
                    "{name}": user_profile.name if user_profile else "friend",
                    "{future_me_persona_summary}": user_profile.future_me_persona_summary
                    if user_profile
                    else "your supportive future self",
                    "{critical_language_elements}": user_profile.key_therapeutic_language
                    if user_profile
                    else "terms that resonate with you",
                    "{core_values_prompt}": user_profile.core_values_summary
                    if user_profile
                    else "your core strengths and values",
                    "{safety_plan_summary}": user_profile.safety_plan_summary
                    if user_profile
                    else "your plan for staying safe",
                }

                for placeholder, value in placeholders.items():
                    if value is not None and placeholder in populated_template:
                        populated_template = populated_template.replace(placeholder, value)
                    elif placeholder in populated_template:
                        logging.warning(
                            f"Value for placeholder {placeholder} is None. Placeholder not replaced with specific user data."
                        )
                return populated_template
            except Exception as e:
                logging.error(f"Error fetching or applying user prompt components for user {user_id}: {e}")
                return base_template_str
        return base_template_str

    async def answer(
        self, message: str, user_id: Optional[str] = None, db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        try:
            user_system_prompt_str = await self.get_user_specific_prompt_str(
                self.base_system_prompt_template_str, user_id, db_session
            )
            user_crisis_prompt_str = await self.get_user_specific_prompt_str(
                self.base_crisis_prompt_template_str, user_id, db_session
            )

            chain_input: Dict[str, Any] = {
                "query": message,
                "input": message,
                "user_system_prompt_str": user_system_prompt_str,
                "user_crisis_prompt_str": user_crisis_prompt_str,
            }

            if hasattr(self, "_get_combined_retriever") and callable(self._get_combined_retriever):
                chain_input["retriever"] = self._get_combined_retriever()

            result = await self.chain.ainvoke(chain_input)
            reply_content = result.get("reply_content", "No specific reply found.")
            return {"reply": cast(str, reply_content)}
        except RuntimeError as e:
            logging.error(f"Runtime error during chain invocation: {e}")
            return {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}
        except Exception as e:
            logging.exception(f"Unexpected error in Orchestrator.answer: {e}")
            return {"reply": "An unexpected error occurred. Please try again."}

    def _load_base_prompt_templates(self) -> None:
        """Loads base system and crisis prompt templates from files."""
        lang = self.settings.APP_DEFAULT_LANGUAGE
        template_dir = "templates"

        try:
            crisis_prompt_path_lang = os.path.join(template_dir, f"crisis_prompt.{lang}.md")
            crisis_prompt_path_generic = os.path.join(template_dir, "crisis_prompt.md")
            if os.path.exists(crisis_prompt_path_lang):
                with open(crisis_prompt_path_lang, "r", encoding="utf-8") as f:
                    self.base_crisis_prompt_template_str = f.read()
            elif os.path.exists(crisis_prompt_path_generic):
                with open(crisis_prompt_path_generic, "r", encoding="utf-8") as f:
                    self.base_crisis_prompt_template_str = f.read()
                logging.warning(
                    f"Crisis prompt for language '{lang}' not found. Falling back to generic 'crisis_prompt.md'."
                )
            else:
                self.base_crisis_prompt_template_str = "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}"
                logging.warning(
                    f"Neither '{crisis_prompt_path_lang}' nor '{crisis_prompt_path_generic}' found. Using hardcoded default crisis prompt."
                )
        except Exception as e:
            logging.error(f"Error loading base crisis prompt: {e}")
            self.base_crisis_prompt_template_str = "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}"

        try:
            system_prompt_path_lang = os.path.join(template_dir, f"system_prompt.{lang}.md")
            system_prompt_path_generic = os.path.join(template_dir, "system_prompt.md")
            if os.path.exists(system_prompt_path_lang):
                with open(system_prompt_path_lang, "r", encoding="utf-8") as f:
                    self.base_system_prompt_template_str = f.read()
            elif os.path.exists(system_prompt_path_generic):
                with open(system_prompt_path_generic, "r", encoding="utf-8") as f:
                    self.base_system_prompt_template_str = f.read()
                logging.warning(
                    f"System prompt for language '{lang}' not found. Falling back to generic 'system_prompt.md'."
                )
            else:
                self.base_system_prompt_template_str = (
                    "Hello {name}. I am your future self. "
                    "Persona: {future_me_persona_summary}. "
                    "Language: {critical_language_elements}. "
                    "Values: {core_values_prompt}. "
                    "Safety: {safety_plan_summary}. "  # Added safety plan summary placeholder
                    "Based on the following context: {context} Answer the question: {input}"
                )
                logging.warning(
                    f"Neither '{system_prompt_path_lang}' nor '{system_prompt_path_generic}' found. Using hardcoded default system prompt."
                )
        except Exception as e:
            logging.error(f"Error loading base system prompt: {e}")
            self.base_system_prompt_template_str = (  # Ensure default also has placeholders
                "Hello {name}. I am your future self. "
                "Persona: {future_me_persona_summary}. "
                "Language: {critical_language_elements}. "
                "Values: {core_values_prompt}. "
                "Safety: {safety_plan_summary}. "
                "Based on the following context: {context} Answer the question: {input}"
            )

    def _load_risk_keywords(self) -> None:
        if self.settings.APP_DEFAULT_LANGUAGE == "he":
            logging.info("Hebrew language selected, but using English risk keywords as placeholder.")
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]
        else:
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]

    def _detect_risk(self, query: str) -> bool:
        if not query:
            return False
        return any(keyword in query.lower() for keyword in self._risk_keywords)

    @staticmethod
    def _build_crisis_chain(prompt_template: ChatPromptTemplate, llm: ChatOpenAI) -> Runnable:
        chain = (
            {
                "query": RunnablePassthrough(),
                "context": RunnableLambda(lambda x: []),
            }
            | prompt_template
            | llm
            | StrOutputParser()
        )
        return RunnableLambda(lambda inputs_dict: {"reply_content": chain.invoke(inputs_dict)})

    @staticmethod
    def _build_rag_chain(
        prompt_template: ChatPromptTemplate, llm: ChatOpenAI, retriever: Optional[BaseRetriever]
    ) -> Runnable:
        logging.debug("Using placeholder _build_rag_chain from Orchestrator base class.")
        chain = (
            {
                "context": RunnableLambda(lambda x: "" if not retriever else "dummy_context_base"),
                "input": RunnablePassthrough(),
            }
            | prompt_template
            | llm
            | StrOutputParser()
        )
        return RunnableLambda(lambda inputs_dict: {"reply_content": chain.invoke(inputs_dict)})


class RagOrchestrator(Orchestrator):
    def __init__(self):
        super().__init__()
        self.theory_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_SESSION)
        self.future_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_FUTURE)
        self.therapist_notes_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THERAPIST_NOTES)
        self.chat_history_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_CHAT_HISTORY)

        self.chain = BranchingChain(self._detect_risk, self._build_crisis_chain, self._build_actual_rag_chain, self.llm)

        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"
        )
        self.summarize_chain = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        """Combines retrievers from all relevant namespaces."""
        from langchain.retrievers import MergerRetriever

        retrievers = [
            self.theory_db.vectordb.as_retriever(search_kwargs={"k": 2}),
            self.plan_db.vectordb.as_retriever(search_kwargs={"k": 2}),
            self.session_db.vectordb.as_retriever(search_kwargs={"k": 2}),
            self.future_db.vectordb.as_retriever(search_kwargs={"k": 2}),
            self.therapist_notes_db.vectordb.as_retriever(search_kwargs={"k": 1}),
            self.chat_history_db.vectordb.as_retriever(search_kwargs={"k": 1}),
        ]
        valid_retrievers = [r for r in retrievers if r is not None]
        if not valid_retrievers:
            logging.error("No valid retrievers found for MergerRetriever.")

            class DummyRetriever(BaseRetriever):
                def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:  # type: ignore
                    return []

                async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:  # type: ignore
                    return []

            return DummyRetriever()
        return MergerRetriever(retrievers=valid_retrievers)

    @staticmethod
    def _build_actual_rag_chain(
        prompt_template: ChatPromptTemplate, llm: ChatOpenAI, retriever: Optional[BaseRetriever]
    ) -> Runnable:
        if not retriever:
            logging.warning("Retriever not provided to _build_actual_rag_chain. RAG will not function as intended.")
            simple_chain = prompt_template | llm | StrOutputParser()
            return RunnableLambda(
                lambda inputs_dict: {
                    "reply_content": simple_chain.invoke({"input": inputs_dict.get("input"), "context": ""})
                }
            )

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        context_retriever_chain = RunnablePassthrough.assign(
            context_docs=RunnableLambda(lambda x: x["input"]) | retriever,
            original_input_message=RunnableLambda(lambda x: x["input"]),
        )

        llm_input_preparation_chain = RunnablePassthrough.assign(
            input=RunnableLambda(lambda x: x["original_input_message"]),
            context=RunnableLambda(lambda x: format_docs(x["context_docs"])),
        )

        answer_generation_chain = llm_input_preparation_chain | prompt_template | llm | StrOutputParser()

        rag_chain_with_sources = RunnablePassthrough.assign(
            answer=answer_generation_chain,
            sources=RunnableLambda(lambda x: [doc.metadata.get("source", "unknown") for doc in x["context_docs"]]),
        )

        full_rag_pipeline = context_retriever_chain | rag_chain_with_sources

        def final_adapter(user_input_dict: Dict) -> Dict:
            rag_result = full_rag_pipeline.invoke(user_input_dict)
            return {"reply_content": rag_result.get("answer"), "sources": rag_result.get("sources", [])}

        return RunnableLambda(final_adapter)

    async def summarize_session(self, session_id: str) -> str:
        logging.info(f"Summarizing session (placeholder): {session_id}")
        try:
            response = await self.summarize_chain.ainvoke({"input": f"Data for session {session_id}..."})
            summary = response
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error summarizing session {session_id}: {e}")
            return f"Summary for {session_id} (unavailable)"

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
    if (
        hasattr(request.app.state, "rag_orchestrator")
        and request.app.state.rag_orchestrator is not None
        and isinstance(request.app.state.rag_orchestrator, RagOrchestrator)
    ):
        return request.app.state.rag_orchestrator

    if not hasattr(request.app.state, "rag_orchestrator") or request.app.state.rag_orchestrator is None:
        logging.warning(
            "RagOrchestrator not found or not initialized in app.state. Creating a new one (this might be unexpected outside of startup)."
        )
        request.app.state.rag_orchestrator = RagOrchestrator()
    return request.app.state.rag_orchestrator
