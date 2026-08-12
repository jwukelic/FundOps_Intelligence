from __future__ import annotations

from app.models import AuditEvent


def make_audit_event(target_type: str, target_id: str, action: str, before: dict, after: dict) -> AuditEvent:
    return AuditEvent(target_type=target_type, target_id=target_id, action=action, before=before, after=after)

