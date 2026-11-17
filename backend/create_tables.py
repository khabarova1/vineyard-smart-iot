import asyncio

from app.database import Base, engine
import app.models


async def create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    print("Таблицы успешно созданы!")


async def main():
    await create_tables()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
