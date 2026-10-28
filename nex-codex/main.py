"""Hosting-panel entry point. Run from the directory containing .env and requirements.txt."""
import asyncio
from nex.bot import main


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
