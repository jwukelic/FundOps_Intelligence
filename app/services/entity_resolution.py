def resolve_account_key(name: str, domain: str | None = None) -> str:
    if domain:
        return domain.lower().strip()
    return name.lower().strip()
