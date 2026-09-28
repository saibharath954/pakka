"""Five-minute check that your keys work before you record the demo.

  python scripts/smoke.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pakka.app import build  # noqa: E402
from pakka.config import Settings  # noqa: E402


async def main() -> None:
    s = Settings.from_env()
    print(f"Hindsight: {s.hindsight_url}  bank={s.bank_id}  LLM: {s.llm_model}  offline={s.offline}")
    agent = build(s)
    await agent.memory.setup()
    print("1/4 bank + playbook mental model ready")
    mems = await agent.memory.recall("subsidy", max_tokens=500)
    print(f"2/4 recall ok ({len(mems)} memories; 0 is fine before seeding)")
    out = await agent.llm.json("Return JSON.", 'Return {"ok": true}')
    print(f"3/4 LLM ok: {out}")
    pb = await agent.memory.playbook()
    print(f"4/4 playbook: {'has content' if pb.get('content') else 'empty (seed history first)'}")
    await agent.memory.close()


if __name__ == "__main__":
    asyncio.run(main())
