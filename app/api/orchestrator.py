# /home/dfront/p/app/api/orchestrator.py
import logging
import os
from typing import Any, Dict, List, Optional, cast

from fastapi import Request
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession  # Added for type hinting

from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor

# Initialize settings once
cfg = get_settings()


# Placeholder for fetching user-specific prompt components from DB
async def get_user_prompt_components_from_db(user_id: str, db_session: AsyncSession) -> Dict[str, str]:
    # In a real implementation, this would query the RDB for user_id
    # For now, returning a placeholder.
    # This data would come from UserTable or a related UserProfileTable
    logging.info(f"Fetching prompt components for user_id: {user_id} (placeholder)")
    # Example: These keys should match placeholders in your base .md templates
    return {
        "future_me_persona_summary": f"This is the future me summary for user {user_id}. I am resilient and have found peace by focusing on small joys and my connection with nature. I often speak calmly and reflectively.",
        "critical_language_elements": "In our therapy, we often discuss 'riding the wave' of emotions and the importance of 'self-compassion'. My future self embodies these.",
        "core_values_prompt": "My core values are authenticity, kindness, and continuous growth.",
        # Add other personalized fields as needed
    }


class BranchingChain:
    def __init__(self, risk_detector, crisis_chain_builder, rag_chain_builder, llm):
        self.risk_detector = risk_detector
        self.crisis_chain_builder = crisis_chain_builder  # Function to build the chain
        self.rag_chain_builder = rag_chain_builder  # Function to build the chain
        self.llm = llm

    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")
        user_specific_system_prompt_template_str = inputs.get("user_system_prompt_str")
        user_specific_crisis_prompt_template_str = inputs.get("user_crisis_prompt_str")
        retriever = inputs.get("retriever")  # For RAG path

        if not user_specific_system_prompt_template_str or not user_specific_crisis_prompt_template_str:
            logging.error("User-specific prompt strings not provided to BranchingChain")
            return {"reply_content": "Error: System configuration issue."}  # Ensure key is reply_content

        system_prompt = ChatPromptTemplate.from_template(user_specific_system_prompt_template_str)
        crisis_prompt = ChatPromptTemplate.from_template(user_specific_crisis_prompt_template_str)

        if self.risk_detector(query):
            crisis_chain = self.crisis_chain_builder(crisis_prompt, self.llm)
            # Crisis chain expects 'query' and 'context' (context is empty for now)
            return await crisis_chain.ainvoke({"query": query, "context": []})
        else:
            rag_chain = self.rag_chain_builder(system_prompt, self.llm, retriever)
            # RAG chain (built by _build_actual_rag_chain) expects {"input": query}
            return await rag_chain.ainvoke({"input": query})


class Orchestrator:
    def __init__(self):
        self.settings = get_settings()
        self._load_base_prompt_templates()  # Loads base templates from files
        self._load_risk_keywords()

        self.llm = ChatOpenAI(
            model=self.settings.LLM_MODEL,
            temperature=self.settings.LLM_TEMPERATURE,
            api_key=self.settings.OPENAI_API_KEY,
        )
        # Pass builder functions to BranchingChain
        self.chain = BranchingChain(
            self._detect_risk,
            self._build_crisis_chain,  # Pass the method itself
            self._build_rag_chain,  # Pass the method itself (placeholder for base Orchestrator)
            self.llm,
        )

    async def get_user_specific_prompt_str(
        self, base_template_str: str, user_id: Optional[str], db_session: Optional[AsyncSession]
    ) -> str:
        if user_id and db_session:
            try:
                user_components = await get_user_prompt_components_from_db(user_id, db_session)
                populated_template = base_template_str
                for key, value in user_components.items():
                    placeholder = "{" + key + "}"
                    if placeholder in populated_template:
                        populated_template = populated_template.replace(placeholder, value)
                    else:
                        logging.warning(
                            f"Placeholder {placeholder} not found in base template. Component for '{key}' not injected."
                        )
                return populated_template
            except Exception as e:
                logging.error(f"Error fetching or applying user prompt components for user {user_id}: {e}")
                return base_template_str  # Fallback to base on error
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
                "input": message,  # Used by RAG chain as primary input
                "user_system_prompt_str": user_system_prompt_str,
                "user_crisis_prompt_str": user_crisis_prompt_str,
            }

            # If this instance is RagOrchestrator, it will have _get_combined_retriever
            if hasattr(self, "_get_combined_retriever") and callable(self._get_combined_retriever):
                chain_input["retriever"] = self._get_combined_retriever()

            result = await self.chain.ainvoke(chain_input)
            reply_content = result.get("reply_content", "No specific reply found.")
            return {"reply": cast(str, reply_content)}
        except RuntimeError as e:
            logging.error(f"Error during chain invocation: {e}")
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
                    "Based on the following context: {context} Answer the question: {input}"
                    # Add placeholders for personalization if you modify the base template files
                    # e.g., "\n\nFuture Me Persona Details:\n{future_me_persona_summary}\nKey Language:\n{critical_language_elements}"
                )
                logging.warning(
                    f"Neither '{system_prompt_path_lang}' nor '{system_prompt_path_generic}' found. Using hardcoded default system prompt."
                )
        except Exception as e:
            logging.error(f"Error loading base system prompt: {e}")
            self.base_system_prompt_template_str = (
                "Based on the following context: {context} Answer the question: {input}"
            )

    def _load_risk_keywords(self) -> None:
        if self.settings.APP_DEFAULT_LANGUAGE == "he":
            logging.info("Hebrew language selected, but using English risk keywords as placeholder.")
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]  # Add Hebrew keywords
        else:
            self._risk_keywords = ["die", "kill myself", "suicide", "hopeless", "end it all"]

    def _detect_risk(self, query: str) -> bool:
        if not query:
            return False
        return any(keyword in query.lower() for keyword in self._risk_keywords)

    @staticmethod
    def _build_crisis_chain(prompt_template: ChatPromptTemplate, llm: ChatOpenAI):
        chain = (
            {
                "query": RunnablePassthrough(),  # Expects a dict with "query"
                "context": RunnableLambda(lambda x: []),  # Provide empty context
            }
            | prompt_template
            | llm
            | StrOutputParser()
        )
        # Wrap the string output in the expected dictionary structure
        return RunnableLambda(lambda inputs_dict: {"reply_content": chain.invoke(inputs_dict)})

    @staticmethod
    def _build_rag_chain(prompt_template: ChatPromptTemplate, llm: ChatOpenAI, retriever: Optional[BaseRetriever]):
        # This is a placeholder for the base Orchestrator if it were ever used directly for RAG.
        # RagOrchestrator overrides this with _build_actual_rag_chain.
        # It won't actually retrieve documents if retriever is None.
        logging.debug("Using placeholder _build_rag_chain from Orchestrator base class.")
        chain = (
            {
                "context": RunnableLambda(
                    lambda x: "" if not retriever else "dummy_context_base"
                ),  # Minimal context if no retriever
                "input": RunnablePassthrough(),  # Expects a dict with "input"
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

        # Override the chain to use the actual RAG chain builder
        self.chain = BranchingChain(
            self._detect_risk,
            self._build_crisis_chain,  # Inherited
            self._build_actual_rag_chain,  # RagOrchestrator's specific RAG chain builder
            self.llm,
        )

        self.summarize_prompt_template = ChatPromptTemplate.from_template(
            "Summarize the following session data concisely: {input}"
        )
        self.summarize_chain = self.summarize_prompt_template | self.llm | StrOutputParser()

    def _get_combined_retriever(self) -> BaseRetriever:
        # Placeholder: In a real app, you'd combine retrievers.
        # For now, using future_db as an example.
        # from langchain.retrievers import MergerRetriever
        # lotr = MergerRetriever(retrievers=[self.theory_db.vectordb.as_retriever(), self.plan_db.vectordb.as_retriever()])
        # return lotr
        return self.future_db.vectordb.as_retriever(search_kwargs={"k": 3})  # Example k value

    @staticmethod
    def _build_actual_rag_chain(
        prompt_template: ChatPromptTemplate, llm: ChatOpenAI, retriever: Optional[BaseRetriever]
    ):
        if not retriever:
            logging.warning("Retriever not provided to _build_actual_rag_chain. RAG will not function as intended.")
            # Fallback to a simple non-RAG chain using the system prompt
            simple_chain = prompt_template | llm | StrOutputParser()
            # Input to this lambda will be a dict like {"input": "user_message"}
            return RunnableLambda(
                lambda inputs_dict: {
                    "reply_content": simple_chain.invoke({"input": inputs_dict.get("input"), "context": ""})
                }
            )

        def format_docs(docs: list[Document]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)

        # Step 1: Retrieve documents based on the input message.
        # Input to this part: {"input": "user_message"}
        # Output of this part: {"context_docs": [Docs], "original_input_message": "user_message"}
        context_retriever_chain = RunnablePassthrough.assign(
            context_docs=RunnableLambda(lambda x: x["input"]) | retriever,
            original_input_message=RunnableLambda(lambda x: x["input"]),
        )

        # Step 2: Prepare inputs for the prompt_template and LLM.
        # Input: {"context_docs": [Docs], "original_input_message": "user_message"}
        # Output: (This is fed directly to prompt_template)
        #   prompt_template expects "input" (user's original message) and "context" (formatted docs string)
        llm_input_preparation_chain = RunnablePassthrough.assign(
            input=RunnableLambda(lambda x: x["original_input_message"]),
            context=RunnableLambda(lambda x: format_docs(x["context_docs"])),
        )

        # Step 3: Generate the answer using the LLM.
        # Input: (output of llm_input_preparation_chain)
        # Output: "llm_answer_string"
        answer_generation_chain = llm_input_preparation_chain | prompt_template | llm | StrOutputParser()

        # Step 4: Combine answer generation with source tracking.
        # Input: {"context_docs": [Docs], "original_input_message": "user_message"} (output of context_retriever_chain)
        # Output: {"answer": "llm_answer_string", "sources": [source_strings]}
        rag_chain_with_sources = RunnablePassthrough.assign(
            answer=answer_generation_chain,  # Takes output of context_retriever_chain
            sources=RunnableLambda(lambda x: [doc.metadata.get("source", "unknown") for doc in x["context_docs"]]),
        )

        # Full RAG pipeline: retrieve -> prepare for LLM & generate answer & track sources
        # Input: {"input": "user_message"}
        # Output: {"answer": "llm_answer_string", "sources": [source_strings]}
        full_rag_pipeline = context_retriever_chain | rag_chain_with_sources

        # Adapt the output to the structure expected by Orchestrator.answer method
        # Input to this lambda: {"input": "user_message"}
        def final_adapter(user_input_dict: Dict) -> Dict:
            rag_result = full_rag_pipeline.invoke(user_input_dict)
            return {
                "reply_content": rag_result.get("answer"),
                "sources": rag_result.get("sources", []),  # Include sources if needed later
            }

        return RunnableLambda(final_adapter)

    async def summarize_session(self, session_id: str) -> str:
        """
        Summarizes a session. For now, it's a placeholder.
        In a real app, this would fetch session data (e.g., from session_db or another source)
        and pass it to the summarization chain.
        """
        logging.info(f"Summarizing session (placeholder): {session_id}")
        try:
            response = await self.summarize_chain.ainvoke({"input": f"Data for session {session_id}..."})
            summary = response
            return cast(str, summary)
        except Exception as e:
            logging.error(f"Error summarizing session {session_id}: {e}")
            return f"Summary for {session_id} (unavailable)"

    async def _summarize_docs_with_chain(self, docs: List[Document]) -> str:
        """Helper to summarize a list of documents using the summarization chain."""
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
        logging.error("RagOrchestrator not found or not initialized in app.state. Creating a new one (unexpected).")
        # Ensure this matches how it's initialized in main.py lifespan
        request.app.state.rag_orchestrator = RagOrchestrator()
    return request.app.state.rag_orchestrator
