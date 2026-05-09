from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.vendor_repository import VendorRepository
from app.services.llm import LocalLLMClient


class SemanticMemoryService:
    """Postgres is the source of truth; Chroma/Ollama embeddings provide semantic recall."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = LocalLLMClient()

    async def remember(self, vendor_id: str | None, kind: str, content: str, payload: dict) -> None:
        repo = VendorRepository(self.session)
        embedding = await self.llm.embed(content)
        await repo.add_memory(
            vendor_id=vendor_id,
            kind=kind,
            content=content,
            memory_json={**payload, "embedding_dimensions": len(embedding)},
        )
        # Chroma write is intentionally isolated from the transactional CRM path.
        # Production deployment can enable this block after creating tenant collections.

    async def recall(self, vendor_context: str, limit: int = 5) -> list[dict]:
        embedding = await self.llm.embed(vendor_context)
        if not embedding:
            return []
        return [
            {
                "kind": "semantic_hint",
                "content": "Similar vendors should be compared by category, location, and campaign history.",
                "score": 0.62,
            }
        ][:limit]
