from __future__ import annotations


def build_downgrade_trace(notes: list[str]) -> list[dict[str, str]]:
    return [
        {
            "note": note,
            "kind": "audit_downgrade" if note.startswith("audit_downgrade:") else "audit_note",
        }
        for note in notes
    ]
