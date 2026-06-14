"""便捷入口：等价于 `python -m bot`。"""
import asyncio

from bot.app import main

if __name__ == "__main__":
    asyncio.run(main())
