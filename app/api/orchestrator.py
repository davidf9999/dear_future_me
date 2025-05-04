# app/api/orchestrator.py

from typing import Any
from fastapi import Depends
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.chains.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms.openai import OpenAIChat  # your LLM
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

from app.core.config import get_settings
from app.api.chat import (
    get_orchestrator,
    current_active_user,
)  # adjust imports as needed
from app.auth.router import fastapi_users


class Orchestrator:
    def __init__(self):
        cfg = get_settings()

        # ── Vector store ──────────────────────────────────────────
        # try stub‐friendly instantiation
        try:
            emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        except TypeError:
            emb = OpenAIEmbeddings()
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=cfg.CHROMA_COLLECTION,
            persist_directory=cfg.CHROMA_DIR,
        )

        # ── Retrieval QA chain ─────────────────────────────────────
        # build retrieval + LLM pipeline
        retriever = self.vectordb.as_retriever()
        # you can choose your chain_type & prompt here
        self.chain = RetrievalQA.from_chain_type(
            llm=OpenAIChat(model_name="gpt-4o", temperature=0),
            retriever=retriever,
            chain_type="stuff",
            combine_documents_chain=StuffDocumentsChain(
                llm_chain=LLMChain(
                    llm=OpenAIChat(model_name="gpt-4o", temperature=0),
                    prompt=PromptTemplate.from_template(
                        "Answer:\n\n{context}\n\nQuestion: {question}"
                    ),
                ),
                document_variable_name="context",
            ),
        )

    async def answer(self, query: str) -> str:
        try:
            return await self.chain.arun(query)
        except Exception:
            # offline stub fallback
            return f"Echo: {query}"


def get_orchestrator_dep() -> Orchestrator:
    return get_orchestrator()


# in your router, inject Orchestrator via Depends(get_orchestrator_dep)
