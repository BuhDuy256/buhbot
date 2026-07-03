"""End-of-run tally and exit code (transition-techniques.md "End of run").

Every article lands in exactly one bucket: added / updated / skipped / failed.
``failed`` is an extra bucket beyond what the assignment asks for, so a failed
article can't silently vanish from the log. The process exits non-zero if any
article failed -- that is what makes ``docker run ... && echo ok`` meaningful.
"""

from dataclasses import dataclass

ADDED = "added"
UPDATED = "updated"
SKIPPED = "skipped"
FAILED = "failed"


@dataclass(frozen=True)
class Outcome:
    article_id: str
    kind: str  # one of ADDED / UPDATED / SKIPPED / FAILED

    @staticmethod
    def skipped(article_id: str) -> "Outcome":
        return Outcome(article_id, SKIPPED)

    @staticmethod
    def confirmed(article_id: str, verdict: str) -> "Outcome":
        # verdict is ADDED or UPDATED -- an article that reached CONFIRMED
        return Outcome(article_id, verdict)

    @staticmethod
    def failed(article_id: str) -> "Outcome":
        return Outcome(article_id, FAILED)


class RunReport:
    def __init__(self) -> None:
        self.outcomes: list[Outcome] = []

    def add(self, outcome: Outcome) -> None:
        self.outcomes.append(outcome)

    def _count(self, kind: str) -> int:
        return sum(1 for o in self.outcomes if o.kind == kind)

    def log(self) -> None:
        added, updated = self._count(ADDED), self._count(UPDATED)
        skipped, failed = self._count(SKIPPED), self._count(FAILED)
        print(
            f"[report] added={added} updated={updated} "
            f"skipped={skipped} failed={failed} total={len(self.outcomes)}"
        )
        if failed:
            failed_ids = [o.article_id for o in self.outcomes if o.kind == FAILED]
            print(f"[report] FAILED article ids: {', '.join(failed_ids)}")

    def exit_code(self) -> int:
        return 1 if self._count(FAILED) else 0
