"""Check your keys before a demo:  python scripts/smoke.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from munshi.app import build  # noqa: E402
from munshi.config import Settings  # noqa: E402


async def main() -> None:
    s = Settings.from_env()
    print(f"Hindsight: {s.hindsight_url}  bank={s.bank_id}  offline={s.offline}  parser={s.parser}")
    agent = build(s)
    await agent.memory.setup()
    print("1/3 bank ready")
    mems = await agent.memory.recall("blue wala", tags=["retailer:R01"], max_tokens=500)
    print(f"2/3 recall ok ({len(mems)} memories; 0 is fine before replay)")
    if agent.llm:
        out = await agent.llm.json("Return JSON.", 'Return {"ok": true}')
        print(f"3/3 LLM ok: {out}")
    else:
        print("3/3 no LLM key: using the rule parser")
    await agent.memory.close()


if __name__ == "__main__":
    asyncio.run(main())
