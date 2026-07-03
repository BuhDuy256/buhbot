"""Tier-1 probe questions.

No labels needed: Tier 1 only checks the *shape* of the reply (bullets, citation
count, real URLs), not which article is correct. The set deliberately mixes:
  - normal in-scope questions (should answer + cite real URLs),
  - one likely to run long (probes the '>5 bullets -> link instead' branch),
  - one out-of-scope (must not fabricate an OptiSigns URL).
Topics are drawn from real fetched articles so they exercise the live KB.
"""

QUESTIONS: list[str] = [
    "How do I access the Troubleshooting page of the OptiSigns Player?",
    "What internet connection checks does the OptiSigns Player run?",
    "What are the whitelist URLs and ports I need to open for OptiSigns?",
    "Give me every single step to fully configure a brand new OptiSigns screen "
    "from unboxing to publishing content.",  # long -> should link, not spill bullets
    "How do I split a screen into multiple zones?",
    "What is the capital of France?",  # out of scope -> must not cite a fake URL
]
