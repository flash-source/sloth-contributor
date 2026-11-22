"""Shared pieces for the SlothContributor file-localization experiment.

build_prompt and parse_files copy src/ai_service.py (suggest_files) as it is in the repo.
resolve_files copies the verify step (main.py + src/file_fetcher.py), except that it looks
paths up in a file tree fetched once per example instead of calling the contents API.
"""
import json
import re
from collections import defaultdict


def build_prompt(title, body):
    clean_body = body[:1500] if body else "No description."
    return f"""Read this GitHub issue and suggest a JSON array of file paths likely causing the bug.
        Issue Title: {title}
        Issue Body: {clean_body}
        Output ONLY a JSON array of strings. Example: ["path/to/file.ext"]. If unsure, output []."""


def parse_files(response):
    """Same regex + json.loads as ai_service.suggest_files. Returns (files, ok).
    ok is False when no valid JSON array could be read from the response."""
    try:
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if not match:
            return [], False
        files = json.loads(match.group(0))
        if not isinstance(files, list):
            return [], False
        return [f for f in files if isinstance(f, str)], True
    except json.JSONDecodeError:
        return [], False


def build_index(tree_paths):
    """basename -> list of full paths, so the fallback does not scan the whole tree."""
    index = defaultdict(list)
    for p in tree_paths:
        index[p.rsplit("/", 1)[-1]].append(p)
    return index


def tree_fallback(index, target):
    """Same scoring as FileFetcher.find_file_in_tree: same filename, score = number of
    matching trailing path parts. Unique best match wins, ties are skipped."""
    wanted = target.strip("/").split("/")
    best, best_score, tie_count = None, 0, 0
    for path in index.get(wanted[-1], []):
        parts = path.split("/")
        score = 0
        for a, b in zip(reversed(parts), reversed(wanted)):
            if a != b:
                break
            score += 1
        if score > best_score:
            best, best_score, tie_count = path, score, 1
        elif score == best_score and score > 0:
            tie_count += 1
    if best and tie_count == 1:
        return best
    return None


def resolve_files(suggested, tree_set, index, k=3):
    """Verify step. Returns (resolved_paths, trace) where trace has one of
    'exact' / 'fallback' / 'dropped' per suggestion. Resolved paths are de-duplicated."""
    resolved, trace = [], []
    for target in suggested[:k]:
        if target in tree_set:
            found, how = target, "exact"
        else:
            found = tree_fallback(index, target)
            how = "fallback" if found else "dropped"
        trace.append(how)
        if found and found not in resolved:
            resolved.append(found)
    return resolved, trace