"""Tier-1.5 probe questions with a scope label.

The only label needed is one bit per question -- in-scope vs out-of-scope -- NOT
a full gold set (which article is the right answer). That single bit lets the
citation check assert the right thing per question:
  - in-scope  -> the answer SHOULD cite 1..3 real 'Article URL:' lines,
  - out-of-scope -> it should cite NONE (any citation is a fabricated source).

The set mixes normal in-scope questions (topics drawn from real fetched
articles), one likely to run long (probes '>5 bullets -> link instead'), and one
out-of-scope (must not answer-with-a-citation).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    question: str
    in_scope: bool


QUESTIONS: list[Probe] = [
    Probe("How do I access the Troubleshooting page of the OptiSigns Player?", True),
    Probe("What internet connection checks does the OptiSigns Player run?", True),
    Probe("What are the whitelist URLs and ports I need to open for OptiSigns?", True),
    Probe(
        "Give me every single step to fully configure a brand new OptiSigns "
        "screen from unboxing to publishing content.",
        True,
    ),  # long -> should link, not spill bullets
    Probe("How do I split a screen into multiple zones?", True),
    Probe("What is the capital of France?", False),  # out of scope
]
