"""Build train/test JSONL for issue -> file localization from JetBrains-Research/lca-bug-localization.

Ground truth is parsed from the dataset's `diff` column: files the fixing PR modified at the
base commit, python only, test files removed, files the PR created removed (they do not
exist at base_sha, so nobody could localize them).

The split is BY REPO, so the fine-tuned model is never tested on a repo it trained on.
The dataset's own train/test split is ignored for that reason.

Usage:  python prepare_data.py --out-dir data
"""
import argparse
import json
import os
import random
import re
from collections import defaultdict

DIFF_BLOCK = re.compile(r"(?m)^(?=diff --git )")
DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)\s*$")


def is_test_file(path):
    parts = path.lower().split("/")
    name = parts[-1]
    return (
        any(p in ("test", "tests") for p in parts[:-1])
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


def truth_from_diff(diff):
    files = []
    for block in DIFF_BLOCK.split(diff or ""):
        first_line = block.split("\n", 1)[0]
        m = DIFF_HEADER.match(first_line)
        if not m:
            continue
        header = block.split("\n@@", 1)[0]
        if re.search(r"(?m)^new file mode", header):
            continue
        path = m.group(1)  # source side, exists at base_sha (also right for renames)
        if path.endswith(".py") and not is_test_file(path) and path not in files:
            files.append(path)
    return files


def build_splits(rows, test_frac=0.2, seed=0, max_per_repo=40, min_files=1, max_files=5):
    rng = random.Random(seed)
    by_repo, seen, stats = defaultdict(list), set(), defaultdict(int)
    for row in rows:
        stats["rows_in"] += 1
        url = row["issue_url"]
        if url in seen:
            stats["dropped_duplicate_issue"] += 1
            continue
        seen.add(url)
        title, body = (row.get("issue_title") or "").strip(), (row.get("issue_body") or "").strip()
        if not title or not body:
            stats["dropped_empty_text"] += 1
            continue
        truth = truth_from_diff(row.get("diff"))
        if not (min_files <= len(truth) <= max_files):
            stats["dropped_file_count"] += 1
            continue
        repo = f"{row['repo_owner']}/{row['repo_name']}"
        by_repo[repo].append(
            {"id": url, "repo": repo, "issue_url": url, "base_sha": row["base_sha"],
             "title": title, "body": body, "files": truth}
        )
    for repo, items in by_repo.items():
        if len(items) > max_per_repo:
            by_repo[repo] = rng.sample(items, max_per_repo)
    repos = sorted(by_repo)
    rng.shuffle(repos)
    n_test = max(1, round(len(repos) * test_frac))
    test_repos, train_repos = set(repos[:n_test]), set(repos[n_test:])
    train = [x for r in sorted(train_repos) for x in by_repo[r]]
    test = [x for r in sorted(test_repos) for x in by_repo[r]]
    stats.update(repos=len(repos), train_repos=len(train_repos), test_repos=len(test_repos),
                 train_examples=len(train), test_examples=len(test))
    return train, test, dict(stats), sorted(train_repos), sorted(test_repos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-per-repo", type=int, default=40)
    args = ap.parse_args()

    from datasets import load_dataset
    ds = load_dataset("JetBrains-Research/lca-bug-localization", "py", split="dev")
    print("columns:", ds.column_names)
    print("changed_files column, first row (check this looks sane):", repr(ds[0]["changed_files"])[:300])

    train, test, stats, train_repos, test_repos = build_splits(
        ds, args.test_frac, args.seed, args.max_per_repo)
    os.makedirs(args.out_dir, exist_ok=True)
    for name, items in (("train", train), ("test", test)):
        with open(os.path.join(args.out_dir, f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for x in items:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(os.path.join(args.out_dir, "repo_split.json"), "w") as f:
        json.dump({"train_repos": train_repos, "test_repos": test_repos}, f, indent=1)
    print(json.dumps(stats, indent=1))
    print("sample:", json.dumps(test[0], ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()