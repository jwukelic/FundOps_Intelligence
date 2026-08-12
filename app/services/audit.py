from datetime import datetime, timezone
from typing import Any


def build_audit_entry(entity_type: str, entity_id: str, field_name: str, old: Any, new: Any) -> dict[str, Any]:
    return {
        "event_at": datetime.now(timezone.utc).isoformat(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "field_name": field_name,
        "old_value": old,
        "new_value": new,
    }
