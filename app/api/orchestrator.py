import logging

from fastapi import Request
from langchain.chains import RetrievalQA
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
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

    async def arun(self, query: str) -> str:
        if self.detect_risk(query):
            logging.warning(f"⚠️  Risk detected: {query!r}")
            return await self.crisis_chain.arun(query)
        return await self.rag_chain.arun(query)


class Orchestrator:
    """
    Top-level orchestrator for /chat/text:
      • risk detection → crisis_chain
      • otherwise → rag_chain (combining theory, plan, session, future_me)
    """

    def __init__(self):
        cfg = get_settings()

        # ── Risk keywords ───────────────────────────────────────────
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

        # ── Crisis chain ────────────────────────────────────────────
        try:
            plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
            retriever = plan_db.vectordb.as_retriever()

            try:
                crisis_md = open("templates/crisis_prompt.md", encoding="utf-8").read()
            except FileNotFoundError:
                crisis_md = (
                    "You are a crisis responder. When the user expresses self-harm intent, "
                    "reply with exactly one coping step from their personal safety plan "
                    "and include a crisis hotline."
                )

            crisis_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(crisis_md),
                    HumanMessagePromptTemplate.from_template("{query}"),
                ]
            )

            self._crisis_chain = RetrievalQA.create_retrieval_chain(
                llm=ChatOpenAI(model_name=cfg.LLM_MODEL, temperature=0.0),
                retriever=retriever,
                combine_documents_chain_kwargs={"prompt": crisis_prompt},
                return_source_documents=False,
            )
        except Exception:

            class _Stub:
                async def arun(self, q):
                    return "⚠️  Crisis chain unavailable."

            self._crisis_chain = _Stub()

        # ── RAG‐QA chain with Future-Me ─────────────────────────────
        try:
            # instantiate all four vector stores
            theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
            plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
            session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)
            future_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_FUTURE)

            # custom combined retriever
            class CombinedRetriever:
                def __init__(self, retrievers):
                    self.retrievers = retrievers

                def get_relevant_documents(self, query: str):
                    docs = []
                    for r in self.retrievers:
                        docs.extend(r.get_relevant_documents(query))
                    return docs

            retrievers = [
                theory_db.vectordb.as_retriever(),
                plan_db.vectordb.as_retriever(),
                session_db.vectordb.as_retriever(),
                future_db.vectordb.as_retriever(),
            ]
            combined_retriever = CombinedRetriever(retrievers)

            system_md = open("templates/system_prompt.md", encoding="utf-8").read()
            rag_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(system_md),
                    HumanMessagePromptTemplate.from_template("{query}"),
                ]
            )

            self._rag_chain = RetrievalQA.create_retrieval_chain(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                retriever=combined_retriever,
                combine_documents_chain_kwargs={"prompt": rag_prompt},
                return_source_documents=False,
            )
        except Exception:

            class _Stub:
                async def arun(self, q):
                    raise RuntimeError("RAG chain unavailable")

            self._rag_chain = _Stub()

        # single entry-point
        self.chain = BranchingChain(
            self._detect_risk, self._crisis_chain, self._rag_chain
        )

    def _detect_risk(self, text: str) -> bool:
        txt = text.lower()
        return any(kw in txt for kw in self._risk_keywords)

    async def answer(self, query: str) -> str:
        try:
            return await self.chain.arun(query)
        except Exception:
            return f"Echo: {query}"


class RagOrchestrator:
    """
    Exposed via /rag/session/{id}/summarize and used as a singleton on app.state.
    """

    def __init__(self):
        cfg = get_settings()
        from app.rag.processor import DocumentProcessor

        self.theory_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_THEORY)
        self.plan_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_PLAN)
        self.session_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_SESSION)
        self.future_db = DocumentProcessor(cfg.CHROMA_NAMESPACE_FUTURE)

        # install a default summarize-chain on session_db.qa
        try:
            chain = load_summarize_chain(
                llm=ChatOpenAI(
                    model_name=cfg.LLM_MODEL,
                    temperature=cfg.LLM_TEMPERATURE,
                ),
                chain_type="stuff",
            )
            self.session_db.qa = chain
        except Exception:

            class _Stub:
                async def arun(self, sid):
                    raise RuntimeError("no QA")

            self.session_db.qa = _Stub()

    async def summarize_session(self, session_id: str) -> str:
        try:
            return await self.session_db.qa.arun(session_id)
        except Exception:
            return f"Summary for {session_id}"
