import logging
import os
from typing import Any, Dict, List, cast

from fastapi import Request
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor

# Initialize settings once
cfg = get_settings()


class BranchingChain:
    def __init__(self, risk_detector, crisis_chain, rag_chain):
        self.risk_detector = risk_detector
        self.crisis_chain = crisis_chain
        self.rag_chain = rag_chain

    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")  # Assuming 'query' is the key for user message
        if self.risk_detector(query):
            # Crisis chain might expect 'query'
            return await self.crisis_chain.ainvoke({"query": query, "context": []})  # Provide empty context if needed
        else:
            # RAG chain might expect 'input' or 'query' and 'context'
            # Ensure inputs are correctly mapped
            return await self.rag_chain.ainvoke({"input": query, "context": []})  # Provide empty context if needed


class Orchestrator:
    def __init__(self):
        self.settings = get_settings()  # Each orchestrator instance gets fresh settings
        self._load_prompts()
        self._load_risk_keywords()

        self.llm = ChatOpenAI(
            model=self.settings.LLM_MODEL,
            temperature=self.settings.LLM_TEMPERATURE,
            api_key=self.settings.OPENAI_API_KEY,
        )
        # Initialize chains (can be overridden by mocks in tests)
        self._crisis_chain = self._build_crisis_chain()
        self._rag_chain = self._build_rag_chain()  # Placeholder, RagOrchestrator will build the real one
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

    async def answer(self, message: str) -> Dict[str, Any]:
        try:
            # BranchingChain will route to the appropriate sub-chain
            # Ensure the input dictionary keys match what BranchingChain expects
            result = await self.chain.ainvoke({"query": message, "input": message})
            # The output key might be 'answer' from RAG or 'result' from Crisis
            reply_content = result.get("answer") or result.get("result", "No specific reply found.")
            return {"reply": cast(str, reply_content)}
        except RuntimeError as e:
            logging.error(f"Error during chain invocation: {e}")
            return {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}
        except Exception as e:  # Catch any other unexpected errors
            logging.exception(f"Unexpected error in Orchestrator.answer: {e}")
            return {"reply": "An unexpected error occurred. Please try again."}

    def _load_prompts(self) -> None:
        """Loads system and crisis prompts based on APP_DEFAULT_LANGUAGE."""
        lang = self.settings.APP_DEFAULT_LANGUAGE
        template_dir = "templates"

        # Try loading language-specific prompt, then generic, then default string
        try:
            crisis_prompt_path_lang = os.path.join(template_dir, f"crisis_prompt.{lang}.md")
            crisis_prompt_path_generic = os.path.join(template_dir, "crisis_prompt.md")
            if os.path.exists(crisis_prompt_path_lang):
                with open(crisis_prompt_path_lang, "r", encoding="utf-8") as f:
                    self.crisis_prompt_template_str = f.read()
            elif os.path.exists(crisis_prompt_path_generic):
                with open(crisis_prompt_path_generic, "r", encoding="utf-8") as f:
                    self.crisis_prompt_template_str = f.read()
                logging.warning(
                    f"Crisis prompt for language '{lang}' not found. Falling back to generic 'crisis_prompt.md'."
                )
            else:
                self.crisis_prompt_template_str = "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}"
                logging.warning(
                    f"Neither '{crisis_prompt_path_lang}' nor '{crisis_prompt_path_generic}' found. Using hardcoded default crisis prompt."
                )
        except Exception as e:
            logging.error(f"Error loading crisis prompt: {e}")
            self.crisis_prompt_template_str = "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}"

        try:
            system_prompt_path_lang = os.path.join(template_dir, f"system_prompt.{lang}.md")
            system_prompt_path_generic = os.path.join(template_dir, "system_prompt.md")
            if os.path.exists(system_prompt_path_lang):
                with open(system_prompt_path_lang, "r", encoding="utf-8") as f:
                    self.system_prompt_template_str = f.read()
            elif os.path.exists(system_prompt_path_generic):
                with open(system_prompt_path_generic, "r", encoding="utf-8") as f:
                    self.system_prompt_template_str = f.read()
                logging.warning(
                    f"System prompt for language '{lang}' not found. Falling back to generic 'system_prompt.md'."
                )
            else:
                self.system_prompt_template_str = (
                    "Based on the following context: {context} Answer the question: {input}"
                )
                logging.warning(
                    f"Neither '{system_prompt_path_lang}' nor '{system_prompt_path_generic}' found. Using hardcoded default system prompt."
                )
        except Exception as e:
            logging.error(f"Error loading system prompt: {e}")
            self.system_prompt_template_str = "Based on the following context: {context} Answer the question: {input}"

        # For type hinting and instantiation
        self.crisis_prompt_template = ChatPromptTemplate.from_template(self.crisis_prompt_template_str)
        self.system_prompt_template = ChatPromptTemplate.from_template(self.system_prompt_template_str)

    def _load_risk_keywords(self) -> None:
        """Loads risk keywords based on language. For now, only English."""
        # TODO: Implement language-specific keyword loading if needed
        if self.settings.APP_DEFAULT_LANGUAGE == "he":
            # Placeholder for Hebrew keywords - for now, uses English as fallback
            # self._risk_keywords = ["מילה1", "מילה2"] # Example Hebrew keywords
            logging.info("Hebrew language selected, but using English risk keywords as placeholder.")
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]
        else:  # Default to English
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]

    def _detect_risk(self, query: str) -> bool:
        """Simple keyword-based risk detection."""
        if not query:  # Handle empty query
            return False
        return any(keyword in query.lower() for keyword in self._risk_keywords)

    def _build_crisis_chain(self):
        # This is a simplified crisis chain.
        # In a real scenario, it might involve RAG from a safety plan.
        # For now, it just uses the prompt and LLM.
        return (
            {
                "query": RunnablePassthrough(),
                "context": RunnableLambda(lambda x: []),
            }  # Pass query, provide empty context
            | self.crisis_prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _build_rag_chain(self):
        # This is a placeholder. The actual RAG chain is built in RagOrchestrator.
        # This basic version is just to make Orchestrator instantiable.
        # It won't actually retrieve documents.
        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        return (
            {
                "context": RunnableLambda(lambda x: []),  # No actual retrieval
                "input": RunnablePassthrough(),
            }
            | self.system_prompt_template
            | self.llm
            | StrOutputParser()
        )


class RagOrchestrator(Orchestrator):
    def __init__(self):
        super().__init__()
        # Initialize DocumentProcessors for each namespace
        self.theory_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_SESSION)
        self.future_db = DocumentProcessor(namespace=self.settings.CHROMA_NAMESPACE_FUTURE)

        # Override the _rag_chain from the parent Orchestrator
        self._rag_chain = self._build_actual_rag_chain()
        # Re-initialize the main chain with the new _rag_chain
        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

        # Summarization chain
        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"  # Using 'input' for consistency
        )
        self.summarize_chain = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        # This is a conceptual example. LangChain's `CombinedRetriever`
        # or a custom retriever would be needed for true multi-namespace search.
        # For simplicity, we'll mock this behavior or use one retriever.
        # For now, let's just use the 'future_me' retriever as a placeholder.
        # In a real app, you'd combine retrievers from theory_db, plan_db, etc.
        # from langchain.retrievers import MergerRetriever # Example
        # lotr = MergerRetriever(retrievers=[self.theory_db.vectordb.as_retriever(), self.plan_db.vectordb.as_retriever()])
        # return lotr
        return self.future_db.vectordb.as_retriever()  # Placeholder

    def _build_actual_rag_chain(self):
        retriever = self._get_combined_retriever()

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain_from_docs = (
            RunnablePassthrough.assign(context=(lambda x: format_docs(x["context"])))
            | self.system_prompt_template
            | self.llm
            | StrOutputParser()
        )

        rag_chain_with_source = RunnablePassthrough.assign(
            answer=rag_chain_from_docs,
            sources=lambda x: [doc.metadata.get("source", "unknown") for doc in x["context"]],
        )
        # The main RAG chain that takes 'input' and retrieves 'context'
        return {"context": retriever, "input": RunnablePassthrough()} | rag_chain_with_source

    async def summarize_session(self, session_id: str) -> str:
        """
        Summarizes a session. For now, it's a placeholder.
        In a real app, this would fetch session data (e.g., from session_db or another source)
        and pass it to the summarization chain.
        """
        # Placeholder: In a real app, retrieve actual session documents
        # For example: docs = self.session_db.query(f"session_id:{session_id}", k=10)
        # For now, just use the session_id as input to the summarize_chain
        logging.info(f"Summarizing session (placeholder): {session_id}")
        try:
            # Assuming the chain returns a dict with "output_text" or similar
            response = await self.summarize_chain.ainvoke(
                {"input": f"Data for session {session_id}..."}
            )  # Pass as "input"
            summary = response  # summarize_chain now directly returns string due to StrOutputParser
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error summarizing session {session_id}: {e}")
            return f"Summary for {session_id} (unavailable)"

    async def _summarize_docs_with_chain(self, docs: List[Document]) -> str:
        """Helper to summarize a list of documents using the summarization chain."""
        if not docs:
            return "No documents provided for summarization."
        # Concatenate document content or handle as appropriate for the chain
        combined_text = "\n\n".join([doc.page_content for doc in docs])
        logging.info(f"Summarizing combined text of {len(docs)} documents.")
        try:
            # Assuming the chain returns a dict with "output_text" or similar
            response = await self.summarize_chain.ainvoke({"input": combined_text})  # Pass as "input"
            summary = response  # summarize_chain now directly returns string
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error in _summarize_docs_with_chain: {e}")
            return "Could not generate summary due to an internal error."


# --- Helper for API Endpoints ---
async def get_orchestrator(request: Request) -> Orchestrator:
    # This ensures that for each request, we use the app.state.rag_orchestrator
    # which was initialized once at startup (lifespan event).
    # If RagOrchestrator is needed, it should be the one in app.state.
    # For now, assuming the base Orchestrator is sufficient or this will be refined.
    if hasattr(request.app.state, "rag_orchestrator") and isinstance(
        request.app.state.rag_orchestrator, RagOrchestrator
    ):
        return request.app.state.rag_orchestrator
    # Fallback or if only base Orchestrator is needed for some endpoints
    # This part might need adjustment based on which orchestrator type is expected.
    # If a simple Orchestrator is ever needed and not the RagOrchestrator singleton:
    # return Orchestrator()
    # For now, always return the singleton if it exists, assuming it's the primary one.
    if not hasattr(request.app.state, "rag_orchestrator"):
        # This case should ideally not happen if lifespan sets it up.
        logging.error("RagOrchestrator not found in app.state. Creating a new one (unexpected).")
        request.app.state.rag_orchestrator = RagOrchestrator()  # Fallback, but investigate if this happens
    return request.app.state.rag_orchestrator
