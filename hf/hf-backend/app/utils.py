from typing import Tuple, Any

def split_repo_id(repo_id: str) -> Tuple[str, str]:
    parts = repo_id.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", repo_id)

def resolve_license(detail_json: dict) -> str | None:
    lic = detail_json.get("license")
    if lic:
        return str(lic)
    card = detail_json.get("cardData") or {}
    card_lic = card.get("license")
    if isinstance(card_lic, str) and card_lic.strip():
        return card_lic.strip()
    if isinstance(card_lic, dict):
        for k in ("name", "id", "spdx"):
            v = card_lic.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    for t in (detail_json.get("tags") or []):
        if isinstance(t, str) and t.lower().startswith("license:"):
            return t.split(":", 1)[1].strip()
    return None
