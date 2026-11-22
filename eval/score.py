"""Score model suggestions against the files the fixing PR changed.

For every example it fetches the repo file tree at base_sha from the GitHub API (cached in
tree_cache.json, needs GITHUB_TOKEN) and runs SlothContributor's verify step on the top-3
suggestions. Reported per model, all on the same set of examples:

  parse_ok          response contained a valid JSON array
  raw_hit@3         a suggested path is exactly a changed file (no verification)
  raw_base_hit@3    a suggested FILENAME matches a changed file's filename (lenient)
  exists            share of suggested paths that exist at base_sha (1 - hallucination rate)
  verified_hit@3    after verify + tree fallback, a resolved file is a changed file
  verified_prec     share of resolved files that are changed files (fallback can pick a real but wrong file)
  text_only         nothing survived verification, app would fall back to text-only

Usage:
  export GITHUB_TOKEN=...
  python score.py --data data/test.jsonl --gens gens/gemma2-2b.jsonl gens/qwen2.5-1.5b.jsonl --regex-baseline
"""
import argparse
import json
import math
import os
import re
import sys
import time

import requests

from common import build_index, parse_files, resolve_files

PATH_TOKEN = re.compile(r"[\w./\\-]+\.py\b")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load_cache(path):
    return json.load(open(path)) if os.path.exists(path) else {}


def get_tree(cache, cache_path, repo, sha, token):
    key = f"{repo}@{sha}"
    if key in cache:
        return cache[key]
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1",
                     headers=headers, timeout=60)
    if r.status_code in (403, 429) and r.headers.get("x-ratelimit-remaining") == "0":
        reset = int(r.headers.get("x-ratelimit-reset", time.time()))
        json.dump(cache, open(cache_path, "w"))
        sys.exit(f"GitHub rate limit hit. Cache saved. Re-run after {time.ctime(reset)} "
                 f"(set GITHUB_TOKEN if you have not).")
    if r.status_code == 200:
        data = r.json()
        entry = {"paths": [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"],
                 "truncated": bool(data.get("truncated"))}
    else:
        entry = {"error": r.status_code}
    cache[key] = entry
    json.dump(cache, open(cache_path, "w"))
    return entry


def regex_candidates(title, body):
    text = f"{title}\n{(body or '')[:1500]}"  # same truncation the app uses
    seen = []
    for tok in PATH_TOKEN.findall(text):
        tok = tok.replace("\\", "/")
        if tok not in seen:
            seen.append(tok)
    return seen


def score_one(suggested, truth, tree):
    tree_set = set(tree["paths"])
    index = build_index(tree["paths"])
    top = suggested[:3]
    truth_set = set(truth)
    truth_names = {t.rsplit("/", 1)[-1] for t in truth}
    resolved, _ = resolve_files(top, tree_set, index)
    return {
        "raw_hit": any(s in truth_set for s in top),
        "raw_base_hit": any(s.strip("/").rsplit("/", 1)[-1] in truth_names for s in top),
        "n_sugg": len(top),
        "n_exist": sum(s in tree_set for s in top),
        "verified_hit": any(r in truth_set for r in resolved),
        "n_resolved": len(resolved),
        "n_resolved_correct": sum(r in truth_set for r in resolved),
        "text_only": len(resolved) == 0,
    }


def summarize(name, per_example, parse_flags):
    n = len(per_example)
    def rate(key):
        k = sum(1 for e in per_example if e[key])
        lo, hi = wilson(k, n)
        return f"{100*k/n:5.1f}% [{100*lo:.0f}-{100*hi:.0f}]"
    sugg = sum(e["n_sugg"] for e in per_example)
    exist = sum(e["n_exist"] for e in per_example)
    res = sum(e["n_resolved"] for e in per_example)
    res_ok = sum(e["n_resolved_correct"] for e in per_example)
    return {
        "model": name, "n": n,
        "parse_ok": f"{100*sum(parse_flags)/max(1,len(parse_flags)):5.1f}%" if parse_flags else "n/a",
        "raw_hit@3": rate("raw_hit"), "raw_base_hit@3": rate("raw_base_hit"),
        "exists": f"{100*exist/max(1,sugg):5.1f}%",
        "verified_hit@3": rate("verified_hit"),
        "verified_prec": f"{100*res_ok/max(1,res):5.1f}%",
        "text_only": rate("text_only"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--gens", nargs="*", default=[])
    ap.add_argument("--regex-baseline", action="store_true",
                    help="also score a no-LLM baseline: path-like tokens found in the issue text")
    ap.add_argument("--tree-cache", default="tree_cache.json")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    data = {}
    for l in open(args.data, encoding="utf-8"):
        r = json.loads(l)
        data[r["id"]] = r

    systems = {}
    for g in args.gens:
        name = os.path.splitext(os.path.basename(g))[0]
        systems[name] = {}
        for l in open(g, encoding="utf-8"):
            r = json.loads(l)
            systems[name][r["id"]] = r["response"]
    # only score ids every model has answered
    ids = [i for i in data if all(i in s for s in systems.values())] if systems else list(data)

    cache = load_cache(args.tree_cache)
    usable = []
    for n_, i in enumerate(ids, 1):
        ex = data[i]
        tree = get_tree(cache, args.tree_cache, ex["repo"], ex["base_sha"], token)
        if "paths" in tree and not tree["truncated"]:
            usable.append(i)
        if n_ % 25 == 0:
            print(f"trees {n_}/{len(ids)}", file=sys.stderr)
    print(f"{len(usable)} of {len(ids)} examples have a complete file tree "
          f"(others dropped: missing sha or truncated tree)")

    rows = []
    names = list(systems) + (["regex-baseline"] if args.regex_baseline else [])
    for name in names:
        per, parse_flags = [], []
        for i in usable:
            ex = data[i]
            tree = cache[f"{ex['repo']}@{ex['base_sha']}"]
            if name == "regex-baseline":
                sugg = regex_candidates(ex["title"], ex["body"])
            else:
                sugg, ok = parse_files(systems[name][i])
                parse_flags.append(ok)
            per.append(score_one(sugg, ex["files"], tree))
        rows.append(summarize(name, per, parse_flags))

    cols = ["model", "n", "parse_ok", "raw_hit@3", "raw_base_hit@3", "exists",
            "verified_hit@3", "verified_prec", "text_only"]
    print("\n" + " | ".join(cols))
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    json.dump(rows, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()