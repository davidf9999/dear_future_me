# app/api/orchestrator.py
from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from app.core.settings import get_settings, Settings


class Orchestrator:
    def __init__(self):
        cfg: Settings = get_settings()
        emb = OpenAIEmbeddings(openai_api_key=cfg.OPENAI_API_KEY)
        # Initialize vector store client
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=cfg.CHROMA_COLLECTION,
            persist_directory=cfg.CHROMA_DIR,
        )
        # Build RetrievalQA chain
        self.chain = RetrievalQA.from_chain_type(
            llm=OpenAI(
                model_name=cfg.LLM_MODEL,
                temperature=cfg.LLM_TEMPERATURE,
            ),
            chain_type="stuff",
            retriever=self.vectordb.as_retriever(),
        )

    async def answer(self, query: str) -> str:
        return await self.chain.arun(query)


# Dependency factory
def get_orchestrator() -> Orchestrator:
    return Orchestrator()
