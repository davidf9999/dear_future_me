import logging
from typing import Any, Dict, List

from fastapi import Request
from langchain.chains import RetrievalQA  # Still used for crisis chain
from langchain.chains import create_retrieval_chain

# Modern chain constructors
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import ChatPromptTemplate
from langchain_core.callbacks.manager import AsyncCallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_openai import ChatOpenAI

from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor


def get_orchestrator() -> "Orchestrator":
    return Orchestrator()


def get_rag_orchestrator(request: Request) -> "RagOrchestrator":
    """
    Returns a singleton RagOrchestrator per app instance.
    """
    orch = getattr(request.app.state, "rag_orchestrator", None)
    if orch is None:
        orch = RagOrchestrator()
        request.app.state.rag_orchestrator = orch
    return orch


class BranchingChain:
    """
    A simple wrapper that either runs crisis_chain or rag_chain
    depending on detect_risk(query).
    """

    def __init__(self, detect_risk, crisis_chain, rag_chain):
        self.detect_risk = detect_risk
        self.crisis_chain = crisis_chain
        self.rag_chain = rag_chain

    async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        query = input_data.get("query")
        if not query:
            logging.error("Query not found in input_data for BranchingChain")
            return {"result": "Error: Query not provided to BranchingChain."}

        if self.detect_risk(query):
            logging.warning(f"⚠️  Risk detected: {query!r}")
            # Crisis chain (RetrievalQA) expects "query"
            return await self.crisis_chain.ainvoke({"query": query})

        # RAG chain (create_retrieval_chain) by default expects "input"
        return await self.rag_chain.ainvoke({"input": query})


class Orchestrator:
    """
    Top-level orchestrator for /chat/text:
      • risk detection → crisis_chain
      • otherwise → rag_chain (combining theory, plan, session, future_me)
    """

    def __init__(self):
        cfg = get_settings()

        self._risk_keywords = [
            "suicide",
            "kill myself",
            "die",
            "death",
            "hurt myself",
            "no reason to live",
            "worthless",
            "hopeless",
        ]

        # ── Crisis chain (still using older RetrievalQA for now) ───────────────────
        try:
            plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
            retriever = plan_db.vectordb.as_retriever()
            try:
                crisis_md = open("templates/crisis_prompt.md", encoding="utf-8").read()
            except FileNotFoundError:
                logging.warning("templates/crisis_prompt.md not found. Using default crisis prompt string.")
                crisis_md = (
                    "You are a crisis responder. When the user expresses self-harm intent, "
                    "reply with exactly one coping step from their personal safety plan "
                    "and include a crisis hotline.\n\n"
                    "Relevant information from safety plan:\n{context}\n\n"
                    "User query: {query}"
                )
            crisis_prompt = ChatPromptTemplate.from_template(crisis_md)
            logging.error(f"DIAGNOSTIC - Crisis Prompt Input Variables: {crisis_prompt.input_variables}")
            self._crisis_chain = RetrievalQA.from_chain_type(
                llm=ChatOpenAI(model_name=cfg.LLM_MODEL, temperature=0.0),
                chain_type="stuff",
                retriever=retriever,
                chain_type_kwargs={"prompt": crisis_prompt},
                return_source_documents=False,
            )
            if hasattr(self._crisis_chain, "combine_documents_chain"):
                logging.error(
                    f"DIAGNOSTIC - Crisis Combine Docs Chain Input Keys: {self._crisis_chain.combine_documents_chain.input_keys}"
                )

        except Exception as exception:
            logging.exception(f"Failed to initialize Crisis chain. Using stub: {exception=}")

            class _StubCrisisChain:
                async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
                    return {"result": "⚠️  Crisis chain unavailable."}

            self._crisis_chain = _StubCrisisChain()

        # ── RAG‐QA chain with Future-Me (using modern constructors) ────────────────
        try:
            theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
            plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
            session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)
            future_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_FUTURE)

            class CombinedRetriever(BaseRetriever):
                retrievers: List[BaseRetriever]

                def _invoke_retrievers_sync(self, query: str) -> List[Document]:
                    docs: List[Document] = []
                    for r_item in self.retrievers:
                        retrieved_docs = r_item.invoke(query)
                        docs.extend(retrieved_docs)
                    return docs

                async def _ainvoke_retrievers_async(self, query: str) -> List[Document]:
                    docs: List[Document] = []
                    for r_item in self.retrievers:
                        retrieved_docs = await r_item.ainvoke(query)
                        docs.extend(retrieved_docs)
                    return docs

                def get_relevant_documents(self, query: str) -> List[Document]:
                    logging.warning(
                        "CombinedRetriever.get_relevant_documents (deprecated) was called. "
                        "Consider using invoke or ainvoke."
                    )
                    return self._invoke_retrievers_sync(query)

                async def _aget_relevant_documents(
                    self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun = None
                ) -> List[Document]:
                    return await self._ainvoke_retrievers_async(query)

            actual_retrievers_list = [
                theory_db.vectordb.as_retriever(),
                plan_db.vectordb.as_retriever(),
                session_db.vectordb.as_retriever(),
                future_db.vectordb.as_retriever(),
            ]
            combined_retriever = CombinedRetriever(retrievers=actual_retrievers_list)

            try:
                system_md = open("templates/system_prompt.md", encoding="utf-8").read()
            except FileNotFoundError:
                logging.error("templates/system_prompt.md not found! RAG chain will use a basic default prompt.")
                system_md = "Based on the following context:\n{context}\n\nAnswer the question: {input}"

            rag_prompt = ChatPromptTemplate.from_template(system_md)
            # system_prompt.md should use {input} for the question and {context} for documents
            logging.error(f"DIAGNOSTIC - RAG Prompt Input Variables: {rag_prompt.input_variables}")

            llm = ChatOpenAI(
                model_name=cfg.LLM_MODEL,
                temperature=cfg.LLM_TEMPERATURE,
            )

            # This chain combines the retrieved documents and the question into a single prompt for the LLM
            question_answer_chain = create_stuff_documents_chain(llm, rag_prompt)
            logging.error(
                f"DIAGNOSTIC - RAG question_answer_chain (stuff_documents_chain) Input Schema Keys: {list(question_answer_chain.input_schema.schema().get('properties').keys()) if hasattr(question_answer_chain, 'input_schema') and hasattr(question_answer_chain.input_schema, 'schema') and question_answer_chain.input_schema.schema().get('properties') else 'N/A (input_schema not as expected)'}"
            )

            # This chain handles retrieving documents and then passing them to the question_answer_chain
            # It expects the user's query under the key "input" by default.
            self._rag_chain = create_retrieval_chain(
                retriever=combined_retriever, combine_docs_chain=question_answer_chain
            )

        except Exception as e:
            logging.exception(f"Failed to initialize main RAG chain. Using stub. Exception: {e}")

            class _StubRagChain:
                async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
                    raise RuntimeError("RAG chain unavailable")

            self._rag_chain = _StubRagChain()

        self.chain = BranchingChain(self._detect_risk, self._crisis_chain, self._rag_chain)

    def _detect_risk(self, text: str) -> bool:
        txt = text.lower()
        return any(kw in txt for kw in self._risk_keywords)

    async def answer(self, query: str) -> str:
        try:
            response_dict = await self.chain.ainvoke({"query": query})

            # create_retrieval_chain output is a dict with "answer"
            # Older RetrievalQA (crisis_chain) output is a dict with "result"
            return response_dict.get("answer") or response_dict.get(
                "result", "Error: No result found in chain response."
            )
        except RuntimeError as e:
            logging.error(f"RuntimeError from RAG chain stub: {e} for query: {query}")
            return "I’m sorry, I’m unable to answer that right now. Please try again later."
        except Exception as e:
            logging.exception(f"Error processing: query='{query}', e={e!r}")
            return "I’m sorry, I’m unable to answer that right now. Please try again later."


class RagOrchestrator:
    """
    Exposed via /rag/session/{id}/summarize and used as a singleton on app.state.
    """

    # Inner class for the stub, to be accessible for isinstance check
    class _StubSummarizeChain:
        async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            raise RuntimeError("Summarization chain (no QA) unavailable")

    def __init__(self):
        cfg = get_settings()
        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)
        self.future_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_FUTURE)

        try:
            self.summarize_chain = load_summarize_chain(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                chain_type="stuff",
            )
        except Exception as e:
            logging.exception(f"Failed to initialize summarization chain. Using stub. Exception: {e}")
            self.summarize_chain = RagOrchestrator._StubSummarizeChain()

    async def summarize_session(self, session_id: str) -> str:
        try:
            if isinstance(self.summarize_chain, RagOrchestrator._StubSummarizeChain):
                await self.summarize_chain.ainvoke({})

            logging.warning(
                f"summarize_session for {session_id}: Actual document retrieval and summarization logic needs implementation."
            )
            # Example:
            # docs_to_summarize = self.session_db.query(f"session_id:{session_id}", k=10) # Fictional
            # if not docs_to_summarize: return f"No documents for session {session_id}"
            # response_dict = await self.summarize_chain.ainvoke({"input_documents": docs_to_summarize})
            # return response_dict.get("output_text", f"Summary for {session_id} (error).")
            return f"Summarization for {session_id} is not fully implemented with document retrieval."

        except RuntimeError as e:
            logging.error(f"Summarization stub error for session {session_id}: {e}")
            return f"Summary for {session_id} (unavailable)"
        except Exception as e:
            logging.exception(f"Error summarizing session: {session_id}, Error: {e!r}")
            return f"Summary for {session_id} (error)"
