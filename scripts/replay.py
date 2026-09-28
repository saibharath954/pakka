"""Replay 8 weeks of WhatsApp orders through memory and save the learning curve.

  python scripts/replay.py                 # wipes the bank, replays with and without memory
  MUNSHI_OFFLINE=1 python scripts/replay.py --out docs/learning_curve.sample.json

After this, the bank holds 8 weeks of learned vocabulary, so the live inbox demo
has something to remember.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from munshi.app import build  # noqa: E402
from munshi.config import Settings  # noqa: E402
from munshi.evaluate import learning_curve  # noqa: E402
from munshi.seed_data import RETAILERS  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/learning_curve.json")
    args = ap.parse_args()

    settings = Settings.from_env()
    agent = build(settings)
    await agent.memory.setup()
    mode = "offline" if settings.offline else "hindsight"

    def progress(phase: str, i: int, n: int) -> None:
        print(f"\r{phase:>7} memory: {i:3d}/{n}", end="", flush=True)
        if i == n:
            print()

    result = await learning_curve(agent, agent.clock(), mode, Path(args.out), progress)
    await agent.setup_dictionaries()
    for r in RETAILERS:
        await agent.memory.refresh_dictionary(r.id)

    print(f"\n{'week':>4} {'with memory':>12} {'without':>9}")
    for w, o in zip(result["with_memory"], result["without_memory"]):
        print(f"{w['week']:>4} {w['auto_rate'] * 100:>11.0f}% {o['auto_rate'] * 100:>8.0f}%")
    t = result["totals"]
    print(f"wrong auto-accepts: {t['with_memory']['auto_wrong']} with memory, {t['without_memory']['auto_wrong']} without")
    print(f"saved to {args.out}")
    await agent.memory.close()


if __name__ == "__main__":
    asyncio.run(main())
