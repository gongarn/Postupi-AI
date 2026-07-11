import asyncio
import sys

from apps.api.main import create_app


async def main() -> int:
    app = create_app()
    async with app.router.lifespan_context(app):
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
