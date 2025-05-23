# app/api/orchestrator.py
# Full file content
import logging
import os
from operator import itemgetter  # Moved to top
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, Request
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from app.api.models import UserData
from app.core.settings import Settings, get_settings
from app.rag.processor import DocumentProcessor

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestrator for handling chat interactions, deciding between RAG and crisis mode.
    """

    def __init__(self, settings: Settings = Depends(get_settings)):
        self.settings = settings
        self.llm = ChatOpenAI(
            model_name=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.rag_orchestrator: Optional[RagOrchestrator] = None
        # Lazily initialize RagOrchestrator or ensure it's passed if always needed

    def _get_rag_orchestrator(self) -> "RagOrchestrator":
        if self.rag_orchestrator is None:
            self.rag_orchestrator = RagOrchestrator(settings=self.settings)
        return self.rag_orchestrator

    def _load_prompt_template(self, file_name: str) -> ChatPromptTemplate:
        """Loads a prompt template from a file."""
        file_path = os.path.join(self.settings.PROMPT_TEMPLATE_DIR, file_name)
        logger.debug(f"Attempting to load prompt template from: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            return ChatPromptTemplate.from_template(template_content)
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {file_path}")
            # Propagate the error; do not use a default.
            raise
        except Exception as e:
            logger.error(f"Error loading prompt template {file_path}: {e}")
            # Propagate the error
            raise

    def _is_crisis_message(self, message: str) -> bool:
        """Determines if a message indicates a crisis situation."""
        return any(keyword.lower() in message.lower() for keyword in self.settings.CRISIS_KEYWORDS)

    async def answer(
        self,
        message: str,
        user_id: Optional[str] = None,
        user_data: Optional[UserData] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes the user's message and returns an appropriate response.
        Switches to crisis mode if keywords are detected.
        Otherwise, uses the RAG orchestrator.
        """
        logger.info(
            f"Orchestrator received message: '{message[:50]}...' for user_id: {user_id}, session_id: {session_id}"
        )

        if self._is_crisis_message(message):
            logger.warning(f"Crisis keywords detected in message from user_id: {user_id}. Switching to crisis mode.")
            # crisis_prompt = self._load_prompt_template(self.settings.CRISIS_PROMPT_FILE) # Variable unused
            # The crisis prompt is loaded by RagOrchestrator itself.

            rag_orchestrator = self._get_rag_orchestrator()
            return await rag_orchestrator.handle_crisis_message(message, user_id, user_data)

        # Proceed with RAG if not a crisis
        rag_orchestrator = self._get_rag_orchestrator()
        return await rag_orchestrator.answer(message, user_id, user_data, session_id)

    async def summarize_session(self, session_id: str, user_id: str) -> Tuple[Optional[str], int]:
        """
        Delegates session summarization to the RagOrchestrator.
        """
        logger.info(f"Orchestrator delegating summarization for session_id: {session_id}, user_id: {user_id}")
        rag_orchestrator = self._get_rag_orchestrator()
        summary, count = await rag_orchestrator.summarize_session(session_id=session_id, user_id=user_id)
        return summary, count


class RagOrchestrator:
    """
    Orchestrates Retrieval Augmented Generation (RAG) by combining multiple retrievers
    and processing queries through an LLM.
    """

    def __init__(self, settings: Settings = Depends(get_settings)):
        self.settings = settings
        self.llm = ChatOpenAI(
            model_name=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.reranker = FlashrankRerank()

        self.theory_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THEORY)
        self.personal_plan_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_PERSONAL_PLAN)
        self.session_data_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_SESSION_DATA)
        self.future_me_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_FUTURE_ME)
        self.therapist_notes_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THERAPIST_NOTES)
        self.chat_summaries_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES)

        self.system_prompt = self._load_prompt_template(self.settings.SYSTEM_PROMPT_FILE)
        self.crisis_prompt = self._load_prompt_template(self.settings.CRISIS_PROMPT_FILE)

        self.ensemble_retriever = self._get_combined_retriever()
        self.rag_chain = self._build_rag_chain(self.system_prompt, self.ensemble_retriever)
        self.crisis_chain = self._build_crisis_chain()

    def _load_prompt_template(self, file_name: str) -> ChatPromptTemplate:
        """Loads a prompt template from a file."""
        file_path = os.path.join(self.settings.PROMPT_TEMPLATE_DIR, file_name)
        logger.debug(f"Attempting to load prompt template from: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            return ChatPromptTemplate.from_template(template_content)
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading prompt template {file_path}: {e}")
            raise

    def _get_retriever_for_db(
        self, doc_processor: DocumentProcessor, search_kwargs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Creates a retriever for a given DocumentProcessor with optional compression."""
        base_retriever = doc_processor.vectordb.as_retriever(search_kwargs=search_kwargs or {"k": 5})
        return base_retriever

    def _get_combined_retriever(self, user_id: Optional[str] = None) -> EnsembleRetriever:
        """
        Creates an ensemble retriever combining various data sources.
        Filters user-specific data if user_id is provided.
        """
        retrievers = [
            self._get_retriever_for_db(self.theory_db, {"k": 3}),
        ]
        weights = [0.6]

        if user_id:
            user_filter = {"user_id": user_id}
            retrievers.extend(
                [
                    self._get_retriever_for_db(self.personal_plan_db, {"k": 2, "filter": user_filter}),
                    self._get_retriever_for_db(self.session_data_db, {"k": 2, "filter": user_filter}),
                    self._get_retriever_for_db(self.future_me_db, {"k": 1, "filter": user_filter}),
                    self._get_retriever_for_db(self.therapist_notes_db, {"k": 1, "filter": user_filter}),
                    self._get_retriever_for_db(self.chat_summaries_db, {"k": 1, "filter": user_filter}),
                ]
            )
            weights.extend([0.1, 0.1, 0.05, 0.05, 0.1])

        return EnsembleRetriever(retrievers=retrievers, weights=weights)

    def _format_docs(self, docs: List[Document]) -> str:
        """Formats retrieved documents into a single string."""
        if not docs:
            return "No relevant information found in the knowledge base."
        return "\n\n".join(
            f"Source {i + 1} (ID: {doc.metadata.get('doc_id', 'N/A')}):\n{doc.page_content}"
            for i, doc in enumerate(docs)
        )

    def _build_rag_chain(self, prompt: ChatPromptTemplate, retriever: EnsembleRetriever):
        """Builds the RAG chain."""
        return (
            {
                "context": retriever | self._format_docs,
                "question": RunnablePassthrough(),
                "user_data": RunnablePassthrough(),
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )

    def _build_crisis_chain(self):
        """Builds the RAG chain specifically for crisis situations, using personal plan."""

        def get_crisis_retriever(input_dict: Dict[str, Any]) -> List[Document]:
            user_id = input_dict.get("user_id")
            question = input_dict.get("question")  # The user's crisis message
            if not user_id:
                logger.warning("No user_id provided for crisis retriever, personal plan cannot be fetched.")
                return []

            personal_plan_retriever = self._get_retriever_for_db(
                self.personal_plan_db, {"k": 3, "filter": {"user_id": user_id}}
            )
            # Use invoke for synchronous retriever, or ainvoke if it's async
            # Assuming _get_retriever_for_db returns a standard LangChain retriever
            return personal_plan_retriever.invoke(question)

        return (
            {
                # Pass the whole input_dict to get_crisis_retriever
                "context": RunnablePassthrough() | get_crisis_retriever | self._format_docs,
                "question": itemgetter("question"),
                "user_data": itemgetter("user_data"),
            }
            | self.crisis_prompt
            | self.llm
            | StrOutputParser()
        )

    async def answer(
        self,
        message: str,
        user_id: Optional[str] = None,
        user_data: Optional[UserData] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Answers a user's query using the RAG chain.
        Includes user_id for context if available.
        """
        logger.info(
            f"RagOrchestrator received message: '{message[:50]}...' for user_id: {user_id}, session_id: {session_id}"
        )

        current_retriever = self._get_combined_retriever(user_id=user_id)
        current_rag_chain = self._build_rag_chain(self.system_prompt, current_retriever)

        chain_input = {"question": message}
        if user_data:
            chain_input["user_data"] = user_data.model_dump()
        else:
            chain_input["user_data"] = {}

        logger.debug(f"Invoking RAG chain with input: {chain_input}")
        response_text = await current_rag_chain.ainvoke(chain_input)

        return {"reply": response_text, "mode": "rag"}

    async def handle_crisis_message(
        self,
        message: str,
        user_id: Optional[str] = None,
        user_data: Optional[UserData] = None,
    ) -> Dict[str, Any]:
        """Handles a crisis message using a specific crisis RAG chain."""
        logger.info(f"Handling crisis message for user_id: {user_id}")

        chain_input: Dict[str, Any] = {"question": message}
        if user_id:
            chain_input["user_id"] = user_id
        if user_data:
            chain_input["user_data"] = user_data.model_dump()
        else:
            chain_input["user_data"] = {}

        logger.debug(f"Invoking crisis RAG chain with input: {chain_input}")
        response_text = await self.crisis_chain.ainvoke(chain_input)

        return {"reply": response_text, "mode": "crisis_rag"}

    async def summarize_session(self, session_id: str, user_id: str) -> Tuple[Optional[str], int]:
        """
        Retrieves all documents for a given session_id and user_id from the
        session_data_db, then summarizes them.
        Returns the summary and the number of documents found.
        """
        logger.info(f"Summarizing session {session_id} for user {user_id}")
        try:
            docs = self.session_data_db.query(
                query="", k=1000, metadata_filter={"session_id": session_id, "user_id": user_id}
            )
        except Exception as e:
            logger.error(f"Error querying session data for session {session_id}, user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving session data for summarization.")

        if not docs:
            logger.warning(f"No documents found for session {session_id}, user {user_id} to summarize.")
            return None, 0

        full_transcript = "\n".join([doc.page_content for doc in docs])

        summarization_prompt_template = PromptTemplate.from_template(
            "Summarize the following conversation transcript concisely:\n\nTranscript:\n{transcript}\n\nSummary:"
        )

        summarization_chain = summarization_prompt_template | self.llm | StrOutputParser()

        try:
            summary = await summarization_chain.ainvoke({"transcript": full_transcript})
            logger.info(f"Successfully summarized {len(docs)} documents for session {session_id}, user {user_id}.")
            return summary, len(docs)
        except Exception as e:
            logger.error(f"Error summarizing transcript for session {session_id}, user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Error during transcript summarization.")


async def get_orchestrator(request: Request) -> Orchestrator:
    if not hasattr(request.app.state, "orchestrator_instance"):
        logger.info("Creating new Orchestrator instance and storing in app.state")
        settings = get_settings()
        request.app.state.orchestrator_instance = Orchestrator(settings=settings)
    return request.app.state.orchestrator_instance


async def get_rag_orchestrator(request: Request) -> RagOrchestrator:
    if not hasattr(request.app.state, "rag_orchestrator_instance"):
        logger.info("Creating new RagOrchestrator instance and storing in app.state")
        settings = get_settings()
        request.app.state.rag_orchestrator_instance = RagOrchestrator(settings=settings)
    return request.app.state.rag_orchestrator_instance
