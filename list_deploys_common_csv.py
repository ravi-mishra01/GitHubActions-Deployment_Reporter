#!/usr/bin/env python3
import os
import re
import csv
import sys
import time
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# Environment selection
# -----------------------------
ENVIRONMENT = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("ENVIRONMENT", "stage")).lower()
if ENVIRONMENT not in ("stage", "prod"):
    raise SystemExit("ENVIRONMENT must be 'stage' or 'prod'")

TAG_PREFIX = "rc" if ENVIRONMENT == "stage" else "rel"

# -----------------------------
# Configuration
# -----------------------------
REPOS_FILE = os.getenv("REPOS_FILE", "repos.txt")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "UnitedOps Microservice Pipeline")

PER_PAGE = int(os.getenv("PER_PAGE", "50"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "8"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "6"))

REQUIRE_SUCCESS = True
DEPLOYED_BY_SOURCE = os.getenv("DEPLOYED_BY_SOURCE", "commit").lower()  # commit|tag

# Output CSV (timestamped)
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
OUT_CSV = os.getenv(
    "OUT_CSV",
    f"{ENVIRONMENT}_latest_deploys_{ts}.csv"
)

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise SystemExit("GITHUB_TOKEN not set")

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

ET = ZoneInfo("America/New_York")

# -----------------------------
# Tag matchers
# -----------------------------
GREEN_TAG = re.compile(rf"^{TAG_PREFIX}.*(?:-|_)?green(?:$|[^a-z])", re.I)
BLUE_TAG  = re.compile(rf"^{TAG_PREFIX}.*(?:-|_)?blue(?:$|[^a-z])", re.I)

# -----------------------------
# Caches
# -----------------------------
_workflow_id_cache = {}
_commit_cache = {}
_tagwho_cache = {}

# -----------------------------
# Helpers
# -----------------------------
def gh_get(session, url, params=None, retries=3):
    for i in range(retries):
        r = session.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code == 401:
            raise SystemExit("401 Bad credentials (token/SSO)")
        if r.status_code in (429, 502, 503, 504):
            time.sleep(1.5 * (i + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()

def parse_dt_utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

def fmt_et(dt):
    return dt.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S %Z")

def sanitize(msg):
    return " ".join((msg or "").replace("\t", " ").splitlines()).strip()

def read_repos():
    with open(REPOS_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def get_workflow_id(session, repo):
    if repo in _workflow_id_cache:
        return _workflow_id_cache[repo]
    data = gh_get(session, f"{API}/repos/{repo}/actions/workflows")
    for wf in data.get("workflows", []):
        if wf["name"].lower() == WORKFLOW_NAME.lower():
            _workflow_id_cache[repo] = wf["id"]
            return wf["id"]
    raise RuntimeError(f"Workflow '{WORKFLOW_NAME}' not found in {repo}")

def iter_runs(session, repo, workflow_id):
    for page in range(1, MAX_PAGES + 1):
        data = gh_get(
            session,
            f"{API}/repos/{repo}/actions/workflows/{workflow_id}/runs",
            {"per_page": PER_PAGE, "page": page},
        )
        runs = data.get("workflow_runs", [])
        if not runs:
            break
        for r in runs:
            yield r

def get_commit_info(session, repo, sha):
    key = (repo, sha)
    if key in _commit_cache:
        return _commit_cache[key]
    c = gh_get(session, f"{API}/repos/{repo}/commits/{sha}")
    msg = sanitize(c["commit"]["message"])
    author = c["commit"].get("author") or {}
    who = f"{author.get('name','unknown')} <{author.get('email','')}>"
    _commit_cache[key] = (who, msg)
    return who, msg

def process_repo(repo):
    session = requests.Session()
    workflow_id = get_workflow_id(session, repo)

    latest_green = None
    latest_blue = None

    for run in iter_runs(session, repo, workflow_id):
        if run["event"] != "push":
            continue
        if REQUIRE_SUCCESS and run["conclusion"] != "success":
            continue

        tag = run.get("head_branch") or ""
        if not tag.startswith(TAG_PREFIX):
            continue

        when = parse_dt_utc(run["updated_at"])
        sha = run["head_sha"]

        if GREEN_TAG.match(tag):
            if not latest_green or when > latest_green["when"]:
                latest_green = {"tag": tag, "sha": sha, "when": when}

        if BLUE_TAG.match(tag):
            if not latest_blue or when > latest_blue["when"]:
                latest_blue = {"tag": tag, "sha": sha, "when": when}

        if latest_green and latest_blue:
            break

    rows = []
    for color, item in (("green", latest_green), ("blue", latest_blue)):
        if not item:
            continue
        who, msg = get_commit_info(session, repo, item["sha"])
        rows.append({
            "repo": repo,
            "environment": ENVIRONMENT,
            "color": color,
            "tag": item["tag"],
            "sha": item["sha"][:7],
            "deployed_by": who,
            "deployment_time_et": fmt_et(item["when"]),
            "commit_comment": msg,
        })
    return rows

# -----------------------------
# Main
# -----------------------------
def main():
    repos = read_repos()
    all_rows = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(process_repo, r) for r in repos]
        for f in as_completed(futures):
            all_rows.extend(f.result())

    fieldnames = [
        "repo",
        "environment",
        "color",
        "tag",
        "sha",
        "deployed_by",
        "deployment_time_et",
        "commit_comment",
    ]

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    print(f"Wrote CSV: {OUT_CSV}")

if __name__ == "__main__":
    main()
