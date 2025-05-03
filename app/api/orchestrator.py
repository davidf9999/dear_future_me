# app/api/orchestrator.py
from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from app.core.settings import settings


class Orchestrator:
    def __init__(self):
        emb = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        # Initialize vector store client
        self.vectordb = Chroma(
            embedding_function=emb,
            collection_name=settings.CHROMA_COLLECTION,
            persist_directory=settings.CHROMA_DIR,
        )
        # Build RetrievalQA chain
        self.chain = RetrievalQA.from_chain_type(
            llm=OpenAI(
                model_name=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
            ),
            chain_type="stuff",
            retriever=self.vectordb.as_retriever(),
        )

    async def answer(self, query: str) -> str:
        """Run the RAG + LLM chain to answer a user query."""
        result = await self.chain.arun(query)
        return result


# Dependency factory
def get_orchestrator() -> Orchestrator:
    return Orchestrator()
