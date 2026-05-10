import asyncio
from app.db.session import AsyncSessionLocal
from app.services.controller import AgentController

async def main():
    async with AsyncSessionLocal() as session:
        controller = AgentController(session)
        res = await controller.process([{"role": "user", "content": "Hello"}])
        print(res)

if __name__ == "__main__":
    asyncio.run(main())
