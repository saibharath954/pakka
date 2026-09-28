"""Load the SunKiran Solar sales history into Hindsight from the command line.

  python scripts/seed.py --reset              # wipe the bank, load all 8 weeks
  python scripts/seed.py --reset --until -40  # only weeks 1-2 (to show the learning curve)
  python scripts/seed.py --since -40          # load the rest later
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pakka.app import build  # noqa: E402
from pakka.config import Settings  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--until", type=int, default=0)
    ap.add_argument("--since", type=int, default=None)
    args = ap.parse_args()

    agent = build(Settings.from_env())
    await agent.memory.setup()
    if args.reset:
        await agent.memory.reset()
        agent.crm.reset()
    out = await agent.replay(until_day=args.until, since_day=args.since)
    print(f"retained {out['retained']} events into bank")
    await asyncio.sleep(1)  # let the background playbook refresh request go out
    await agent.memory.close()


if __name__ == "__main__":
    asyncio.run(main())
