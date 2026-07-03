"""Tier-1 eval runner: ask the live Assistant each probe question N times, run
the deterministic format checks, and report per-check ADHERENCE RATES.

Usage:
    OPTIBOT_ASSISTANT_ID=asst_... uv run python -m evals.run_eval
    OPTIBOT_ASSISTANT_ID=asst_... OPTIBOT_EVAL_RUNS=5 uv run python -m evals.run_eval

Why repeat each question (OPTIBOT_EVAL_RUNS, default 1): the Assistant's
compliance with the system prompt is *probabilistic*, not guaranteed -- even at
temperature 0 the output varies run to run. A single pass can't tell "obeys" from
"got lucky once". Running each probe N times turns "it doesn't always obey the
format" from a gut feeling into a measured rate (e.g. citation adherence 82%),
which is the honest way to report generation behavior you cannot deterministically
enforce.

Prerequisite -- the Assistant must already exist in the Playground with:
  * the verbatim OptiBot system prompt,
  * the 'optibot-kb' vector store attached (run the pipeline once first so the
    store exists),
  * sampling set to temperature = 0 and top_p = 1 (max determinism for a support
    RAG bot: no creativity is wanted, and at temp 0 top_p is effectively inert so
    it is left at 1 rather than adding a second knob. NOTE: temp 0 reduces
    variance, it does NOT guarantee identical output -- which is exactly why this
    runner measures a rate).
Set its id in OPTIBOT_ASSISTANT_ID.

This is a regression baseline: fix this set, change ONE thing (chunk size,
cleaning, header template, ...), re-run, compare the rates. That is how a change
is shown to be real progress rather than a guess.
"""

import os
import sys
from collections import defaultdict

from src import zendesk
from src.settings import load_settings

from . import assistant, checks
from .questions import QUESTIONS

_RULES = ("bullet_limit", "citation", "urls_real")


def _runs() -> int:
    try:
        return max(1, int(os.getenv("OPTIBOT_EVAL_RUNS", "1")))
    except ValueError:
        return 1


def main() -> int:
    # Assistant answers can contain smart quotes / em-dashes that crash a Windows
    # cp1252 console; force UTF-8 output so a run never dies mid-scorecard.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    settings = load_settings()
    client = settings.client()

    assistant_id = os.getenv("OPTIBOT_ASSISTANT_ID")
    if not assistant_id:
        print("ERROR: set OPTIBOT_ASSISTANT_ID to the deployed Assistant's id.")
        return 2

    # Validate cited URLs against the FULL catalog, not the uploaded subset: a
    # real answer may cite a body link to any real article (dev caps the uploaded
    # set, but a real cite is still not a hallucination).
    valid_ids = zendesk.fetch_all_article_ids()

    runs = _runs()
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # rule -> [passed, total]
    leak = [0, 0]  # [out-of-scope runs that emitted a citation, out-of-scope runs]
    all_pass = True

    print(f"[eval] format checks against assistant {assistant_id} "
          f"({runs} run(s)/question)\n")
    for i, probe in enumerate(QUESTIONS, start=1):
        scope = "in-scope" if probe.in_scope else "out-of-scope"
        print(f"Q{i} [{scope}]: {probe.question}")

        q_tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        sample: str | None = None
        for _ in range(runs):
            answer = assistant.ask(client, assistant_id, probe.question)
            if sample is None:
                sample = answer.replace("\n", " ")[:120]
            for r in checks.run_checks(answer, valid_ids, in_scope=probe.in_scope):
                agg[r.rule][0] += r.passed
                agg[r.rule][1] += 1
                q_tally[r.rule][0] += r.passed
                q_tally[r.rule][1] += 1
                all_pass = all_pass and r.passed
                if not probe.in_scope and r.rule == "citation":
                    leak[1] += 1
                    leak[0] += not r.passed

        print(f"    sample: {sample}{'...' if sample and len(sample) >= 120 else ''}")
        for rule in _RULES:
            p, t = q_tally[rule]
            if t:
                print(f"    {rule:<12} {p}/{t} run(s) passed ({100 * p / t:.0f}%)")
        print()

    print("[eval] adherence rates (probabilistic -- measured, not guaranteed):")
    for rule in _RULES:
        p, t = agg[rule]
        if t:
            print(f"    {rule:<14} {100 * p / t:5.1f}%  ({p}/{t})")
    if leak[1]:
        print(f"    {'oos_leak_rate':<14} {100 * leak[0] / leak[1]:5.1f}%  "
              f"({leak[0]}/{leak[1]} out-of-scope run(s) emitted a citation)")

    total = sum(v[1] for v in agg.values())
    passed = sum(v[0] for v in agg.values())
    print(f"\n[eval] {passed}/{total} checks passed across "
          f"{len(QUESTIONS)} question(s) x {runs} run(s)")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
