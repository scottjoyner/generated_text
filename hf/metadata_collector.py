#!/usr/bin/env python3
"""
Scrape ALL Hugging Face models (no license filtering) and save:
  - models_index.jsonl  : id, author, name
  - models_full.jsonl   : curated fields incl. resolved license
  - models_raw.jsonl    : FULL raw /api/models/{id} JSON per line
  - cache/<author__name>.json : per-repo cached JSON

Extras:
  - Resolves license from multiple places (detail.license, cardData.license,
    tags like 'license:apache-2.0').
  - Rate limiting + retries + resume.
"""

import os
import re
import json
import time
import argparse
import requests
from requests.adapters import HTTPAdapter, Retry

BASE = "https://huggingface.co"
LIST_URL = f"{BASE}/api/models"
DETAIL_URL_TMPL = f"{BASE}/api/models/{{repo_id}}"

def make_session(token: str | None, timeout: int = 30) -> requests.Session:
    s = requests.Session()
    headers = {
        "User-Agent": "hf-model-scraper/1.1 (+https://huggingface.co)",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    s.headers.update(headers)
    retries = Retry(
        total=10,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.request = _wrap_with_timeout(s.request, timeout)
    return s

def _wrap_with_timeout(request_func, timeout):
    def wrapped(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return request_func(method, url, **kwargs)
    return wrapped

LINK_RE = re.compile(r'\s*<([^>]+)>;\s*rel="([^"]+)"')

def parse_link_header(link_header: str | None) -> dict[str, str]:
    out = {}
    if not link_header:
        return out
    for part in link_header.split(","):
        m = LINK_RE.match(part.strip())
        if m:
            url, rel = m.groups()
            out[rel] = url
    return out

def ensure_dir(p): os.makedirs(p, exist_ok=True); return p
def safe_filename(repo_id: str) -> str: return repo_id.replace("/", "__")

def split_repo_id(repo_id: str):
    parts = repo_id.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", repo_id)

def list_models(session, limit=100, full=False, start_url=None, sleep=0.5, max_items=-1):
    url = start_url or LIST_URL
    params = {"limit": str(limit), "full": "true" if full else "false"}
    seen = 0
    while True:
        resp = session.get(url, params=params if "cursor=" not in url else None)
        if resp.status_code >= 400:
            print(f"[WARN] list_models HTTP {resp.status_code}: {resp.text[:200]}")
            break
        items = resp.json()
        if not isinstance(items, list):
            print(f"[WARN] Unexpected list payload: {str(items)[:200]}")
            break
        for it in items:
            yield it
            seen += 1
            if sleep > 0: time.sleep(sleep)
            if max_items > 0 and seen >= max_items: return
        links = parse_link_header(resp.headers.get("Link"))
        nxt = links.get("next")
        if not nxt: return
        url = nxt

def fetch_model_detail(session, repo_id, sleep=0.5, cache_dir=None):
    cache_path = None
    if cache_dir:
        ensure_dir(cache_dir)
        cache_path = os.path.join(cache_dir, f"{safe_filename(repo_id)}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    url = DETAIL_URL_TMPL.format(repo_id=repo_id)
    resp = session.get(url)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "5"))
        wait_s = max(5, retry_after)
        print(f"[RATE LIMIT] 429. Sleeping {wait_s}s …")
        time.sleep(wait_s)
        resp = session.get(url)
    resp.raise_for_status()
    data = resp.json()
    if cache_path:
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
    if sleep > 0: time.sleep(sleep)
    return data

def resolve_license(detail_json: dict) -> str | None:
    """
    Try multiple sources to capture license consistently:
    1) top-level 'license'
    2) model card: cardData.license (string or dict)
    3) tags: entries like 'license:apache-2.0'
    """
    # 1) top-level
    lic = detail_json.get("license")
    if lic: return str(lic)

    # 2) cardData
    card = detail_json.get("cardData") or {}
    card_lic = card.get("license")
    if isinstance(card_lic, str) and card_lic.strip():
        return card_lic.strip()
    if isinstance(card_lic, dict):
        # some model cards nest extra info
        for k in ("name", "id", "spdx"):  # best guess keys
            if isinstance(card_lic.get(k), str) and card_lic[k].strip():
                return card_lic[k].strip()

    # 3) tags
    for t in detail_json.get("tags", []) or []:
        if isinstance(t, str) and t.lower().startswith("license:"):
            return t.split(":", 1)[1].strip()

    return None  # unknown / custom / missing

def run(out_dir: str, sleep: float, max_items: int, resume: bool, list_full: bool):
    token = os.getenv("HUGGINGFACE_TOKEN")
    out_dir   = ensure_dir(out_dir)
    cache_dir = ensure_dir(os.path.join(out_dir, "cache"))
    state_path = os.path.join(out_dir, "state.json")
    index_path = os.path.join(out_dir, "models_index.jsonl")
    full_path  = os.path.join(out_dir, "models_full.jsonl")
    raw_path   = os.path.join(out_dir, "models_raw.jsonl")

    session = make_session(token)

    start_url = None
    if resume and os.path.exists(state_path):
        try:
            state = json.load(open(state_path, "r"))
            start_url = state.get("next_url") or None
            print("[RESUME] Continuing from saved pagination URL.")
        except Exception:
            pass

    total = 0
    with open(index_path, "a", encoding="utf-8") as idx_f, \
         open(full_path,  "a", encoding="utf-8") as full_f, \
         open(raw_path,   "a", encoding="utf-8") as raw_f:

        for item in list_models(session, limit=100, full=list_full, start_url=start_url, sleep=sleep, max_items=max_items):
            repo_id = item.get("modelId") or item.get("id")
            if not repo_id:
                continue

            detail = fetch_model_detail(session, repo_id, sleep=sleep, cache_dir=cache_dir)

            # Always write RAW (full metadata) one-per-line
            raw_f.write(json.dumps(detail, ensure_ascii=False) + "\n")

            author, name = split_repo_id(detail.get("id", repo_id))
            idx_line = {"id": detail.get("id", repo_id), "author": author, "name": name}
            idx_f.write(json.dumps(idx_line, ensure_ascii=False) + "\n")

            lic = resolve_license(detail)
            card = detail.get("cardData") or {}
            curated = {
                "id": detail.get("id", repo_id),
                "author": author,
                "name": name,
                "private": detail.get("private", False),
                "sha": detail.get("sha"),
                "lastModified": detail.get("lastModified"),
                "pipeline_tag": detail.get("pipeline_tag"),
                "tags": detail.get("tags", []),
                "downloads": detail.get("downloads"),
                "likes": detail.get("likes"),
                "gated": detail.get("gated", False),
                "license": lic,  # unified license
                "license_raw": detail.get("license"),  # original field for reference
                "siblings": [s.get("rfilename") for s in detail.get("siblings", []) if isinstance(s, dict)],
                "library_name": detail.get("library_name"),
                "config": detail.get("config"),
                "card_summary": card.get("summary") or card.get("description"),
                "card_params": card.get("params"),
                "card_model_size": card.get("model_size"),
                "card_datasets": card.get("datasets"),
                "card_languages": card.get("language") or card.get("languages"),
            }
            full_f.write(json.dumps(curated, ensure_ascii=False) + "\n")

            total += 1
            if total % 200 == 0:
                print(f"[PROGRESS] {total} repos processed …")

        # Save a minimal state marker to indicate completion (no cursor to store at the end)
        json.dump({"next_url": None}, open(state_path, "w"))

    print("[DONE] Wrote:")
    print(f"  - {index_path}")
    print(f"  - {full_path}")
    print(f"  - {raw_path}")
    print(f"  - Cached per-repo JSON under: {cache_dir}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="hf_models_out", help="Output directory")
    ap.add_argument("--sleep", type=float, default=0.5, help="Per-request polite delay (seconds)")
    ap.add_argument("--max", type=int, default=-1, help="Max number of repos for testing; -1 = all")
    ap.add_argument("--resume", action="store_true", help="Resume from last saved pagination point")
    ap.add_argument("--list-full", action="store_true", help="Ask list endpoint for fuller items (slower)")
    args = ap.parse_args()
    run(args.out, args.sleep, args.max, args.resume, args.list_full)
