#!/usr/bin/env python3
"""
Merge a short permissions list with the full model metadata.

- Left-joins model_permissions.csv (short list) with model_metadata.csv (rich rows)
- Robustly extracts a repo_id from either:
    * canonical Hugging Face URL (https://huggingface.co/<org>/<repo> or /<repo>)
    * "huggingface-<org>-<repo>" slug (name_hf_slug)
    * explicit repo_id column
    * model_name that already looks like "<org>/<repo>" or "<repo>"

Output:
  model_permissions_enriched.csv  (original permissions columns + appended metadata)
  Adds:
    - hf_url    : canonical HF URL (prefers metadata canonical_url; else permission URL)
    - match_repo_id : extracted key used to join (for audit)
    - match_status  : "matched"/"unmatched"

Usage:
  python merge_permissions_with_metadata.py \
      --permissions model_permissions.csv \
      --metadata model_metadata.csv \
      --out model_permissions_enriched.csv
"""

import argparse
import pandas as pd
from typing import Optional

def is_clean_hf_url(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("https://huggingface.co/"):
        return False
    tail = url.split("huggingface.co/")[-1].split("?")[0].split("#")[0].strip("/")
    if not tail:
        return False
    parts = tail.split("/")
    # Accept single-tenant (/bert-base-uncased) or org/repo
    return len(parts) in (1, 2)

def extract_repo_id_from_url(url: str) -> Optional[str]:
    if not isinstance(url, str) or "huggingface.co/" not in url:
        return None
    tail = url.split("huggingface.co/")[-1].split("?")[0].split("#")[0].strip("/")
    if not tail:
        return None
    parts = [p for p in tail.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if len(parts) == 1:
        return parts[0]
    return None

def repo_id_from_slug(slug: str) -> Optional[str]:
    """
    Convert 'huggingface-<org>-<repo-with-hyphens>' → '<org>/<repo-with-hyphens>'
    or 'huggingface-<repo>' (single-tenant) → '<repo>'
    """
    if not isinstance(slug, str):
        return None
    s = slug.strip()
    if not s.lower().startswith("huggingface-"):
        return None
    rest = s[len("huggingface-"):]
    if not rest:
        return None
    parts = rest.split("-")
    if len(parts) >= 2:
        org = parts[0]
        repo = "-".join(parts[1:])
        return f"{org}/{repo}"
    # single-tenant repo like "huggingface-bert-base-uncased"
    return rest

def looks_like_repo_id(s: str) -> bool:
    return isinstance(s, str) and ("/" in s or s.strip() != "")

def best_repo_id_from_row(row, prefer_columns):
    """
    Try columns in order to extract a repo_id for matching.
    prefer_columns is a list of column names to check in order (common ones tried below).
    """
    # First pass: URLs
    for col in prefer_columns:
        if col in row and isinstance(row[col], str) and is_clean_hf_url(row[col]):
            rid = extract_repo_id_from_url(row[col])
            if rid:
                return rid

    # Slug
    for col in ["name_hf_slug", "hf_slug", "slug"]:
        v = row.get(col)
        rid = repo_id_from_slug(v) if isinstance(v, str) else None
        if rid:
            return rid

    # Explicit repo_id
    for col in ["repo_id", "model_id"]:
        v = row.get(col)
        if isinstance(v, str) and v.strip():
            return v.strip().strip("/")

    # model_name might already be "<org>/<repo>" or "<repo>"
    mn = row.get("model_name")
    if isinstance(mn, str) and mn.strip():
        s = mn.strip().strip("/")
        if "/" in s or s:  # accept single-tenant
            return s

    # As last resort: parse any 'url' even if not cleaned (may still be HF)
    url_any = row.get("url")
    if isinstance(url_any, str) and "huggingface.co/" in url_any:
        rid = extract_repo_id_from_url(url_any)
        if rid:
            return rid

    return None

def main():
    ap = argparse.ArgumentParser(description="Append model metadata to a permissions list by matching repo_id/URL/slug.")
    ap.add_argument("--permissions", required=True, help="Path to model_permissions.csv (short list).")
    ap.add_argument("--metadata", required=True, help="Path to model_metadata.csv (full metadata).")
    ap.add_argument("--out", default="model_permissions_enriched.csv", help="Output CSV path.")
    args = ap.parse_args()

    perm_df = pd.read_csv(args.permissions)
    meta_df = pd.read_csv(args.metadata)

    # Ensure metadata has a usable repo_id
    if "repo_id" not in meta_df.columns:
        # Try to derive from canonical_url or name_hf_slug
        tmp_repo = []
        for _, r in meta_df.iterrows():
            rid = None
            if "canonical_url" in meta_df.columns and isinstance(r.get("canonical_url"), str):
                rid = extract_repo_id_from_url(r.get("canonical_url"))
            if not rid and "name_hf_slug" in meta_df.columns and isinstance(r.get("name_hf_slug"), str):
                rid = repo_id_from_slug(r.get("name_hf_slug"))
            if not rid and "url" in meta_df.columns and isinstance(r.get("url"), str):
                rid = extract_repo_id_from_url(r.get("url"))
            if not rid and "model_name" in meta_df.columns and isinstance(r.get("model_name"), str):
                s = r.get("model_name").strip().strip("/")
                rid = s if s else None
            tmp_repo.append(rid)
        meta_df["repo_id"] = tmp_repo

    # Deduplicate metadata on repo_id (keep first)
    meta_df = meta_df.dropna(subset=["repo_id"])
    meta_df = meta_df.drop_duplicates(subset=["repo_id"], keep="first")

    # Compute a match key for permissions
    prefer_cols_perm = []
    # Prefer specifically-named URL columns if they exist
    for c in ["canonical_url", "updated_url", "url"]:
        if c in perm_df.columns:
            prefer_cols_perm.append(c)

    match_keys = []
    for _, row in perm_df.iterrows():
        rid = best_repo_id_from_row(row, prefer_columns=prefer_cols_perm)
        match_keys.append(rid)
    perm_df["match_repo_id"] = match_keys

    # Merge (left join so we keep all permissions rows)
    merged = perm_df.merge(
        meta_df,
        how="left",
        left_on="match_repo_id",
        right_on="repo_id",
        suffixes=("", "_meta")
    )

    # Derive a single HF URL column for convenience
    def pick_hf_url(row):
        for col in ["canonical_url", "updated_url", "url"]:
            v = row.get(col)
            if isinstance(v, str) and v.startswith("https://huggingface.co/"):
                return v
        return ""

    merged["hf_url"] = merged.apply(pick_hf_url, axis=1)
    merged["match_status"] = merged["repo_id"].apply(lambda x: "matched" if isinstance(x, str) and x.strip() else "unmatched")

    # Reorder: original permission cols first, then metadata (without duplicating obvious overlaps)
    perm_cols = list(perm_df.columns)  # includes match_repo_id
    meta_cols = [c for c in meta_df.columns if c not in perm_cols]
    # Put a few helpful columns near the front
    front_extras = ["hf_url", "match_status"]
    final_cols = perm_cols + [c for c in front_extras if c not in perm_cols] + [c for c in meta_cols if c not in front_extras]

    merged = merged[final_cols]

    merged.to_csv(args.out, index=False)
    print(f"Wrote {args.out}  (rows: {len(merged)}, matched: {(merged['match_status']=='matched').sum()}, unmatched: {(merged['match_status']=='unmatched').sum()})")

if __name__ == "__main__":
    main()
