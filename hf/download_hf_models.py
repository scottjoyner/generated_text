#!/usr/bin/env python3
"""
HF downloader + optional MinIO/S3 mirror.

New flags (all optional):
  --s3-endpoint   e.g. https://minio.minio-tenant.svc.cluster.local:443
  --s3-bucket     e.g. hf-models
  --s3-prefix     e.g. library/ (prepended to <org>/<repo>/...)
  --s3-access-key / --s3-secret-key  (or rely on env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
  --s3-region     default us-east-1
  --s3-secure / --no-s3-secure       default: secure
  --s3-verify     path to CA bundle file or 'false' (default: SA CA path)
  --manifest      write & upload a manifest.json per repo
Env:
  HUGGINGFACE_TOKEN respected (as before).
"""

import argparse, csv, fnmatch, json, os, shutil, sys, time, mimetypes, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
import pandas as pd
import requests
from tqdm import tqdm

# --- optional S3 ---
try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:
    boto3 = None

CACHE_DIR = "cache"
DEFAULT_OUT_DIR = "hf_models"
DEFAULT_REVISION = "main"
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "").strip()
BASE_HEADERS = {"User-Agent": "hf-downloader/1.1"}
if HUGGINGFACE_TOKEN:
    BASE_HEADERS["Authorization"] = f"Bearer {HUGGINGFACE_TOKEN}"

DEFAULT_WEIGHT_PATTERNS = [
    "*.safetensors", "*.bin", "*safetensors.index.json", "*bin.index.json",
    "*.onnx", "*.tflite", "*.gguf", "*.pt",
    "config.json", "generation_config.json", "preprocessor_config.json",
    "tokenizer.json", "tokenizer.model", "spiece.model", "vocab.*", "merges.txt",
    "special_tokens_map.json",
]

def is_hf_url(url: str) -> bool: return isinstance(url, str) and url.startswith("https://huggingface.co/")
def sanitize_repo_id(repo_id: str) -> str: return repo_id.strip().strip("/")
def extract_repo_id_from_url(url: str) -> Optional[str]:
    if not is_hf_url(url): return None
    bits = url.split("huggingface.co/")[-1].split("?")[0].split("#")[0].strip("/").split("/")
    return f"{bits[0]}/{bits[1]}" if len(bits) >= 2 else None

def resolve_repo_id(row: dict) -> Optional[str]:
    for key in ("repo_id", "model_id"):
        if key in row and isinstance(row[key], str) and "/" in row[key]:
            return sanitize_repo_id(row[key])
    if "url" in row and isinstance(row["url"], str):
        rid = extract_repo_id_from_url(row["url"])
        if rid: return sanitize_repo_id(rid)
    if "model_name" in row and isinstance(row["model_name"], str) and "/" in row["model_name"]:
        return sanitize_repo_id(row["model_name"])
    return None

def cache_path_for_repo(repo_id: str) -> Path:
    return Path(CACHE_DIR) / f"{repo_id.replace('/', '__')}.json"

def load_or_fetch_model_json(repo_id: str, revision: str, sleep_s: float = 0.5) -> Optional[dict]:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    cpath = cache_path_for_repo(repo_id)
    if cpath.exists():
        try: return json.loads(cpath.read_text())
        except Exception: pass
    api_url = f"https://huggingface.co/api/models/{repo_id}"
    try:
        r = requests.get(api_url, headers=BASE_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        cpath.write_text(json.dumps(data, indent=2))
        time.sleep(sleep_s)
        return data
    except Exception as e:
        print(f"[WARN] API error for {repo_id}: {e}", file=sys.stderr); return None

def list_siblings(model_json: dict) -> List[dict]:
    return [{"rfilename": s.get("rfilename"), "size": s.get("size")}
            for s in (model_json.get("siblings") or []) if s.get("rfilename")]

def choose_files(siblings: List[dict], patterns: List[str]) -> List[dict]:
    return [s for s in siblings if any(fnmatch.fnmatch(s["rfilename"], p) for p in patterns)]

def make_dest_path(root: Path, repo_id: str, rfilename: str) -> Path:
    return root / repo_id / rfilename

def ensure_parent(p: Path) -> None: p.parent.mkdir(parents=True, exist_ok=True)

def link_or_copy(src: Path, dst: Path) -> None:
    ensure_parent(dst)
    try:
        if dst.exists(): return
        os.link(src, dst)
    except Exception:
        shutil.copy2(src, dst)

def download_file(repo_id: str, rfilename: str, dest: Path, headers: Dict[str, str], revision: str, expected_size: Optional[int]=None) -> bool:
    ensure_parent(dest)
    url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{rfilename}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    resume_pos = tmp.stat().st_size if tmp.exists() else 0
    if dest.exists() and (expected_size is None or dest.stat().st_size == expected_size):
        return True
    h = dict(headers)
    if resume_pos > 0: h["Range"] = f"bytes={resume_pos}-"
    with requests.get(url, headers=h, stream=True, timeout=60) as r:
        if r.status_code == 416: tmp.rename(dest); return True
        if r.status_code in (401,403): print(f"[WARN] Access denied: {repo_id}:{rfilename}", file=sys.stderr); return False
        if r.status_code not in (200,206): print(f"[WARN] HTTP {r.status_code} {url}", file=sys.stderr); return False
        mode = "ab" if r.status_code == 206 and resume_pos > 0 else "wb"
        if mode == "wb" and tmp.exists(): tmp.unlink(missing_ok=True)
        total = (expected_size - resume_pos) if (expected_size and r.status_code == 206) else (expected_size or None)
        chunk_iter = r.iter_content(chunk_size=1024*1024)
        with open(tmp, mode) as f, tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024,
                                        desc=f"{repo_id}/{Path(rfilename).name}", leave=False) as pbar:
            for ch in chunk_iter:
                if not ch: continue
                f.write(ch); 
                if pbar.total is not None: pbar.update(len(ch))
    if expected_size and tmp.stat().st_size != expected_size:
        print(f"[INFO] Size mismatch {dest.name}: got {tmp.stat().st_size} != {expected_size}", file=sys.stderr)
    tmp.rename(dest); return True

# ---------- S3 helpers ----------
def build_s3(args):
    if not (args.s3_endpoint and args.s3_bucket):
        return None
    if boto3 is None:
        raise RuntimeError("boto3 not installed in image; enable it in the container.")
    ak = args.s3_access_key or os.getenv("AWS_ACCESS_KEY_ID")
    sk = args.s3_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
    if not (ak and sk):
        raise RuntimeError("S3 creds missing: set --s3-access-key/--s3-secret-key or AWS_* env.")
    verify = False if str(args.s3_verify).lower() in ("false","0","no") else (args.s3_verify or "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
    return boto3.client(
        "s3",
        endpoint_url=args.s3_endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        region_name=args.s3_region or "us-east-1",
        use_ssl=args.s3_secure,
        verify=verify,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"})
    )

def s3_key(prefix: str, repo_id: str, rfilename: str) -> str:
    prefix = (prefix or "").lstrip("/"); 
    return "/".join([p for p in [prefix, repo_id, rfilename] if p])

def guess_ct(path: Path) -> str:
    ct, _ = mimetypes.guess_type(path.name)
    return ct or "application/octet-stream"

def sha256sum(path: Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for blk in iter(lambda: f.read(1024*1024), b""):
            h.update(blk)
    return h.hexdigest()

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Download HF models and optionally mirror to S3/MinIO.")
    ap.add_argument("--input", default="models.csv")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--copy-dir", default=None)
    ap.add_argument("--revision", default=DEFAULT_REVISION)
    ap.add_argument("--patterns", default="weights")
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--manifest", action="store_true", help="Write per-repo manifest.json (and upload if S3 enabled).")
    # S3 opts
    ap.add_argument("--s3-endpoint", default=os.getenv("S3_ENDPOINT"))
    ap.add_argument("--s3-bucket", default=os.getenv("S3_BUCKET"))
    ap.add_argument("--s3-prefix", default=os.getenv("S3_PREFIX", ""))
    ap.add_argument("--s3-access-key", default=os.getenv("S3_ACCESS_KEY"))
    ap.add_argument("--s3-secret-key", default=os.getenv("S3_SECRET_KEY"))
    ap.add_argument("--s3-region", default=os.getenv("S3_REGION", "us-east-1"))
    ap.add_argument("--s3-secure", action="store_true", default=True)
    ap.add_argument("--no-s3-secure", dest="s3-secure", action="store_false")
    ap.add_argument("--s3-verify", default=os.getenv("S3_VERIFY"))  # path or 'false'
    args = ap.parse_args()

    out_root = Path(args.out_dir); out_root.mkdir(parents=True, exist_ok=True)
    copy_root = Path(args.copy_dir) if args.copy_dir else None
    if copy_root: copy_root.mkdir(parents=True, exist_ok=True)
    patterns = DEFAULT_WEIGHT_PATTERNS if args.patterns=="weights" else (["*"] if args.patterns=="all" else [p.strip() for p in args.patterns.split(",") if p.strip()])
    try:
        df = pd.read_csv(args.input)
    except Exception:
        rows = list(csv.DictReader(open(args.input, newline="", encoding="utf-8")))
        import pandas as pd as _pd  # type: ignore
        df = _pd.DataFrame(rows)    # fallback

    s3 = None
    if args.s3_endpoint and args.s3_bucket:
        s3 = build_s3(args)

    processed: Set[str] = set()
    ok_models, fail_models = 0, 0

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Models"):
        rid = resolve_repo_id(row.to_dict())
        if not rid or rid in processed: 
            if not rid: fail_models += 1
            continue
        processed.add(rid)

        meta = load_or_fetch_model_json(rid, args.revision, sleep_s=args.sleep)
        if not meta: print(f"[WARN] Skipping {rid}: no metadata", file=sys.stderr); fail_models += 1; continue
        siblings = list_siblings(meta); 
        if not siblings: print(f"[WARN] No files listed for {rid}", file=sys.stderr); fail_models += 1; continue
        files = siblings if patterns == ["*"] else choose_files(siblings, patterns)
        if not files: ok_models += 1; continue

        if args.dry_run:
            print(f"[DRY] {rid}:")
            for s in files: print(f"   - {s['rfilename']} ({s.get('size','?')} bytes)")
            ok_models += 1; continue

        per_repo_manifest = {"repo": rid, "files": []}
        all_ok = True
        for s in files:
            rfilename = s["rfilename"]; size = s.get("size")
            dest = make_dest_path(out_root, rid, rfilename)
            if not download_file(rid, rfilename, dest, BASE_HEADERS, args.revision, expected_size=size):
                all_ok = False; continue
            if copy_root:
                try: link_or_copy(dest, copy_root / rid / rfilename)
                except Exception as e: print(f"[WARN] mirror copy failed: {e}", file=sys.stderr)
            # optional S3
            if s3:
                key = s3_key(args.s3_prefix, rid, rfilename)
                extra = {"ContentType": guess_ct(dest)}
                s3.upload_file(str(dest), args.s3_bucket, key, ExtraArgs=extra)
            if args.manifest:
                per_repo_manifest["files"].append({
                    "path": f"{rid}/{rfilename}",
                    "size": int(Path(dest).stat().st_size),
                    "sha256": sha256sum(dest)
                })

        if args.manifest:
            mpath = out_root / rid / "manifest.json"
            ensure_parent(mpath)
            mpath.write_text(json.dumps(per_repo_manifest, indent=2))
            if s3:
                s3.upload_file(str(mpath), args.s3_bucket, s3_key(args.s3_prefix, rid, "manifest.json"),
                               ExtraArgs={"ContentType": "application/json"})

        ok_models += 1 if all_ok else 0
        fail_models += 0 if all_ok else 1

    print(f"\nDone. OK: {ok_models} | Issues: {fail_models} | Unique models: {len(processed)}")
    if not HUGGINGFACE_TOKEN:
        print("Note: set HUGGINGFACE_TOKEN for gated/private repos.", file=sys.stderr)

if __name__ == "__main__":
    main()
