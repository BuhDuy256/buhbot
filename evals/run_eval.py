"""Tier-1 eval runner: ask the live Assistant each probe question, run the
deterministic format checks, print a scorecard, exit non-zero on any failure.

Usage:
    OPTIBOT_ASSISTANT_ID=asst_... uv run python -m evals.run_eval

Prerequisite: the Assistant must already exist in the Playground with the
verbatim system prompt and the 'optibot-kb' vector store attached (run the
pipeline once first so the store exists). Set its id in OPTIBOT_ASSISTANT_ID.

This is a regression baseline: fix this set, change ONE thing (chunk size,
cleaning, ...), re-run, compare the pass count. That is how a change is shown to
be real progress rather than a guess.
"""

import os
import sys

from src import zendesk
from src.settings import load_settings

from . import assistant, checks
from .questions import QUESTIONS


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
    # real answer may cite a body link to any real article (state: dev caps the
    # uploaded set, but a real cite is still not a hallucination).
    valid_ids = zendesk.fetch_all_article_ids()

    total = passed = 0
    print(f"[eval] Tier-1.5 format checks against assistant {assistant_id}\n")
    for i, probe in enumerate(QUESTIONS, start=1):
        answer = assistant.ask(client, assistant_id, probe.question)
        results = checks.run_checks(answer, valid_ids, in_scope=probe.in_scope)
        q_pass = all(r.passed for r in results)

        scope = "in-scope" if probe.in_scope else "out-of-scope"
        print(f"Q{i} [{scope}]: {probe.question}")
        snippet = answer.replace("\n", " ")[:120]
        print(f"    answer: {snippet}{'...' if len(answer) > 120 else ''}")
        for r in results:
            total += 1
            passed += r.passed
            mark = "PASS" if r.passed else "FAIL"
            print(f"    [{mark}] {r.rule}: {r.detail}")
        print(f"    => {'OK' if q_pass else 'FAILED'}\n")

    print(f"[eval] {passed}/{total} checks passed across {len(QUESTIONS)} question(s)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
