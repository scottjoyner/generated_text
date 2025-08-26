#!/usr/bin/env python3
"""
Fix/normalize Hugging Face model URLs in a CSV by looking up repos via the HF API.

- Reads input CSV with at least: model_name, url
- Produces an updated_url column (canonical: https://huggingface.co/<repo_id>)
- Avoids non-HF domains (/tree, /blob, metatext.io, haystack.deepset.ai, etc.)
- Uses model_name as the primary search key; also mines hints from bad URLs.
- Caches all API responses to ./cache to reduce API calls.
- Respects HUGGINGFACE_TOKEN if set (useful for private/gated repos).

Usage:
  python fix_hf_urls.py --input models_enriched.csv --output models_enriched_fixed.csv

Optionally edit inplace:
  python fix_hf_urls.py --input models_enriched.csv --inplace

This script plays nicely with your existing scrape.py and download.py; see notes at bottom.
"""

import argparse
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests

CACHE_DIR = "cache"
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "").strip()
HEADERS = {"User-Agent": "hf-url-normalizer/1.0"}
if HUGGINGFACE_TOKEN:
    HEADERS["Authorization"] = f"Bearer {HUGGINGFACE_TOKEN}"

HF_API_MODEL = "https://huggingface.co/api/models/{repo_id}"
HF_API_SEARCH = "https://huggingface.co/api/models?search={q}&limit=50"

# Small set of org tokens often embedded in non-HF URLs or model_name prefixes
KNOWN_ORGS = {
    "facebook", "google", "microsoft", "Cohere", "OpenAssistant",
    "tiiuae", "meta-llama", "xlnet", "EleutherAI", "stabilityai",
    "bigscience", "Salesforce", "deepset", "sentence-transformers",
    "allenai", "t5", "laion", "mosaicml", "decapoda-research",
}

# ---------------------------------------------------------------------------

def _cache_read(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return None

def _cache_write(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", s.lower()).strip("_")

def is_clean_hf_url(url: str) -> bool:
    """
    A "clean" HF URL is just https://huggingface.co/<repo_id> (no /tree, /blob, /resolve, etc.).
    repo_id may be:
      - "org/name"
      - "name" (official single-tenant repositories, e.g., "bert-base-uncased")
    """
    try:
        if not isinstance(url, str):
            return False
        u = urlparse(url)
        if u.scheme not in ("http", "https"):
            return False
        if u.netloc != "huggingface.co":
            return False
        path = u.path.strip("/")
        if not path or path.count("/") > 1:
            return False
        # Reject extra path suffixes like /tree/... or /resolve/...
        parts = path.split("/")
        if len(parts) == 1:
            # ok single-tenant repo: /bert-base-uncased
            return True
        if len(parts) == 2:
            # org/repo
            return True
        return False
    except Exception:
        return False

def repo_id_from_clean_hf_url(url: str) -> Optional[str]:
    if not is_clean_hf_url(url):
        return None
    path = urlparse(url).path.strip("/")
    return path or None

def guess_from_non_hf_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to mine hints from non-HF URLs like:
      https://metatext.io/models/facebook-bart-large-cnn
      https://site/path/.../Cohere-embed-english-v3.0
    Returns (org_hint, repo_hint_name) where:
      org_hint may be None or a likely org string
      repo_hint_name is the likely repo name part (no org)
    """
    try:
        if not isinstance(url, str) or not url:
            return (None, None)
        p = urlparse(url)
        last = Path(p.path).name  # last path component
        last = last.strip("/")
        if not last:
            return (None, None)

        # common separators
        name = last.replace("__", "-").replace("_", "-")

        # org-prefix forms like facebook-bart-large-cnn
        m = re.match(r"^([A-Za-z0-9_.-]+)[\-_](.+)$", name)
        if m:
            org = m.group(1)
            rest = m.group(2)
            if org in KNOWN_ORGS:
                return (org, rest)

        # Otherwise: return something usable as a search query
        return (None, name)
    except Exception:
        return (None, None)

def clean_model_query(model_name: str) -> Tuple[str, List[str]]:
    """
    Normalize model_name to a reasonable search query and extract org hints.

    Examples:
      "Huggingface-Cohere-Cohere-embed-english-light-v3.0" -> ("Cohere-embed-english-light-v3.0", ["Cohere"])
      "huggingface-bart-large-cnn" -> ("bart-large-cnn", ["facebook"])
    """
    if not isinstance(model_name, str):
        return ("", [])

    s = model_name.strip()

    # Remove obvious "huggingface" noise prefixes (case-insensitive)
    s = re.sub(r"(?i)^huggingface[-_]+", "", s)

    # If it contains an org/repo already, use that plainly as query
    if "/" in s:
        return (s.strip("/"), [])

    # Replace underscores with hyphens for HF norm
    s = s.replace("__", "-").replace("_", "-")

    # If it looks like org-thing (e.g., Cohere-embed-english...), peel org to a hint
    parts = s.split("-")
    org_hints = []
    if parts and parts[0] in KNOWN_ORGS:
        org_hints.append(parts[0])

    # Special cases to help steer search
    if s.lower().startswith("bart-"):
        org_hints.append("facebook")
    if s.lower().startswith("roberta-"):
        org_hints.append("facebook")
    if s.lower().startswith("t5"):
        org_hints.append("google")
    if s.lower().startswith("deberta"):
        org_hints.append("microsoft")

    # Strip duplicate org prefix like "Cohere-Cohere-embed-..."
    if len(parts) >= 2 and parts[0].lower() == parts[1].lower():
        s = "-".join(parts[1:])

    return (s, list(dict.fromkeys(org_hints)))  # dedupe hints

def hf_get_model(repo_id: str, sleep_s: float = 0.25) -> Optional[dict]:
    """
    GET /api/models/{repo_id}. Cache by repo_id.
    """
    cpath = Path(CACHE_DIR) / f"model_{repo_id.replace('/', '__')}.json"
    data = _cache_read(cpath)
    if data is not None:
        return data

    url = HF_API_MODEL.format(repo_id=repo_id)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        _cache_write(cpath, data)
        time.sleep(sleep_s)
        return data
    except Exception:
        return None

def hf_search(q: str, sleep_s: float = 0.25) -> List[dict]:
    """
    GET /api/models?search=...
    Cache by query text.
    """
    if not q:
        return []
    key = _slug(q)
    cpath = Path(CACHE_DIR) / f"search_{key}.json"
    cached = _cache_read(cpath)
    if cached is not None:
        return cached.get("items", [])

    url = HF_API_SEARCH.format(q=requests.utils.quote(q))
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        items = r.json()
        # Normalize to list of dicts
        if isinstance(items, dict) and "items" in items:
            out_items = items["items"]
        else:
            out_items = items if isinstance(items, list) else []

        _cache_write(cpath, {"items": out_items})
        time.sleep(sleep_s)
        return out_items
    except Exception:
        return []

def repo_id_from_search_item(item: dict) -> Optional[str]:
    # HF search payloads sometimes expose 'modelId' or 'id'
    for k in ("modelId", "id"):
        v = item.get(k)
        if isinstance(v, str) and v:
            return v.strip("/")
    return None

def score_candidate(repo_id: str, query_name: str, org_hints: List[str]) -> float:
    """
    Score similarity using a mix of:
      - name similarity vs repo tail
      - small bonus if org matches a hint
    """
    tail = repo_id.split("/")[-1]
    sim = difflib.SequenceMatcher(None, query_name.lower(), tail.lower()).ratio()
    bonus = 0.0
    if len(repo_id.split("/")) == 2:
        org = repo_id.split("/")[0]
        if org in org_hints:
            bonus += 0.08
    return sim + bonus

def try_direct_candidates(cands: List[str]) -> Optional[str]:
    """
    For a few direct guesses, try exact GET /api/models/{rid}.
    Return the first that exists.
    """
    for rid in cands:
        data = hf_get_model(rid)
        if data:
            return rid
    return None

def resolve_repo_for_row(model_name: str, url: Optional[object]) -> Optional[str]:
    """
    Resolve to a repo_id ("org/name" or "name") by:
      1) If url already a clean HF URL, accept it.
      2) Guess from non-HF url hints.
      3) Use model_name-based search, plus any org hints, to pick best match.
      4) Try a few direct candidates against /api/models.
    """
    # Always coerce to safe strings
    url_s = url if isinstance(url, str) else ""
    name_s = model_name if isinstance(model_name, str) else ""

    # 1) Already clean HF
    if url_s and is_clean_hf_url(url_s):
        rid = repo_id_from_clean_hf_url(url_s)
        if rid:
            return rid

    # 2) Hints from non-HF URL
    org_hint_from_url, repo_hint_from_url = (None, None)
    if url_s and "huggingface.co" not in url_s:
        org_hint_from_url, repo_hint_from_url = guess_from_non_hf_url(url_s)

    # 3) Clean model name → query
    query, org_hints = clean_model_query(name_s or "")
    if org_hint_from_url and org_hint_from_url not in org_hints:
        org_hints.append(org_hint_from_url)

    # 4) Try direct candidates
    direct: List[str] = []
    if org_hints and query:
        for org in org_hints:
            direct.append(f"{org}/{query}")
    if repo_hint_from_url:
        if org_hint_from_url:
            direct.insert(0, f"{org_hint_from_url}/{repo_hint_from_url}")
        direct.append(repo_hint_from_url)  # single-tenant fallback
    if query:
        direct.append(query)  # single-tenant fallback

    rid = try_direct_candidates(direct)
    if rid:
        return rid

    # 5) Fall back to HF search
    search_terms = []
    if org_hint_from_url and repo_hint_from_url:
        search_terms.append(f"{org_hint_from_url} {repo_hint_from_url}")
    if query:
        search_terms.append(query)
    if name_s:
        search_terms.append(name_s)

    best = None
    best_score = 0.0
    for q in search_terms:
        items = hf_search(q)
        for it in items:
            cand = repo_id_from_search_item(it)
            if not cand:
                continue
            # Filter weird paths
            if "/" in cand and len(cand.split("/")) != 2:
                continue
            sc = score_candidate(cand, query or q, org_hints)
            if sc > best_score:
                best, best_score = cand, sc
        if best and best_score >= 0.88:
            break

    return best


def to_updated_url(repo_id: Optional[str]) -> str:
    return f"https://huggingface.co/{repo_id}" if repo_id else ""

def process_csv(input_csv: str, output_csv: Optional[str], inplace: bool, sleep_s: float = 0.15) -> Tuple[int, int]:
    df = pd.read_csv(input_csv)
    if "model_name" not in df.columns or "url" not in df.columns:
        raise ValueError("Input CSV must have at least columns: model_name, url")

    resolved_cache: Dict[Tuple[str, str], str] = {}
    updated_urls: List[str] = []
    ok, miss = 0, 0

    for idx, row in df.iterrows():
        mn = row.get("model_name")
        model_name = mn if isinstance(mn, str) else ""
        url = row.get("url")  # keep raw; we’ll type-check inside resolver

        key = (model_name, url if isinstance(url, str) else "")

        if key in resolved_cache:
            updated_urls.append(resolved_cache[key])
            continue

        repo_id = resolve_repo_for_row(model_name, url)
        updated = to_updated_url(repo_id)

        if updated:
            ok += 1
        else:
            miss += 1

        resolved_cache[key] = updated
        updated_urls.append(updated)

        # small sleep to be nice on the API in aggressive loops
        time.sleep(sleep_s)

    df["updated_url"] = updated_urls

    out_path = input_csv if inplace else (output_csv or input_csv.replace(".csv", "_fixed.csv"))
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[fix_hf_urls] Wrote: {out_path}  (resolved={ok}, unresolved={miss}, rows={len(df)})")
    return ok, miss

def main():
    ap = argparse.ArgumentParser(description="Normalize model URLs to canonical Hugging Face repos.")
    ap.add_argument("--input", required=True, help="Input CSV (needs model_name,url).")
    ap.add_argument("--output", default=None, help="Output CSV path (default: <input>_fixed.csv). Ignored if --inplace.")
    ap.add_argument("--inplace", action="store_true", help="Edit the input CSV in place.")
    ap.add_argument("--sleep", type=float, default=0.15, help="Sleep between API lookups (seconds).")
    args = ap.parse_args()

    try:
        process_csv(args.input, args.output, args.inplace, sleep_s=args.sleep)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
