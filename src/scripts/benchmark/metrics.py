"""Metric functions (no file access, easy to test).

Single-value fields: accuracy, macro-F1, per-label precision/recall/F1.
Multi-value fields: exact match, mean Jaccard, micro/macro precision/recall/F1.
Text: ROUGE-1 and ROUGE-L F1 (implemented here), BLEU via sacrebleu.
An empty value counts as its own label "(none)", so "no target" vs "no target" is correct.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from constants import NONE_LABEL


# ------------------------------------------------------------------ labels
def is_empty(value) -> bool:
    return value is None or (isinstance(value, float) and value != value) or str(value).strip() in {"", "nan", "None"}


def fold(text: str) -> str:
    """Comparable form of a label: case, subscript and whitespace do not matter."""
    text = str(text).replace("CO₂", "CO2").replace("₂", "2")
    return re.sub(r"\s+", " ", text).strip().casefold()


def single_label(value) -> str:
    return NONE_LABEL if is_empty(value) else fold(value)


def label_set(value) -> frozenset[str]:
    if is_empty(value):
        return frozenset({NONE_LABEL})
    parts = {fold(p) for p in str(value).split(";") if p.strip()}
    return frozenset(parts) or frozenset({NONE_LABEL})


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


# ---------------------------------------------------------- single fields
def single_metrics(gold: list[str], pred: list[str]) -> tuple[dict, list[dict]]:
    """Gold and pred are already normalised with ``single_label``."""
    n = len(gold)
    correct = sum(g == p for g, p in zip(gold, pred))
    set_rows = [(g, p) for g, p in zip(gold, pred) if g != NONE_LABEL]
    labels = sorted(set(gold) | set(pred))
    per_label = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        precision, recall, f1 = prf(tp, fp, fn)
        per_label.append({"label": label, "support": tp + fn, "predicted": tp + fp,
                          "precision": precision, "recall": recall, "f1": f1})
    scored = [row for row in per_label if row["support"] > 0]
    summary = {
        "n": n,
        "accuracy": correct / n if n else 0.0,
        "macro_f1": sum(r["f1"] for r in scored) / len(scored) if scored else 0.0,
        "n_gold_set": len(set_rows),
        "accuracy_gold_set": sum(g == p for g, p in set_rows) / len(set_rows) if set_rows else float("nan"),
    }
    return summary, per_label


# ----------------------------------------------------------- multi fields
def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def multi_metrics(gold: list[frozenset], pred: list[frozenset]) -> tuple[dict, list[dict]]:
    """Gold and pred are label sets from ``label_set``. "(none)" is not counted as a label in P/R/F1."""
    n = len(gold)
    labels = sorted((set().union(*gold, *pred) if n else set()) - {NONE_LABEL})
    per_label = []
    total_tp = total_fp = total_fn = 0
    for label in labels:
        tp = sum(label in g and label in p for g, p in zip(gold, pred))
        fp = sum(label not in g and label in p for g, p in zip(gold, pred))
        fn = sum(label in g and label not in p for g, p in zip(gold, pred))
        total_tp, total_fp, total_fn = total_tp + tp, total_fp + fp, total_fn + fn
        precision, recall, f1 = prf(tp, fp, fn)
        per_label.append({"label": label, "support": tp + fn, "predicted": tp + fp,
                          "precision": precision, "recall": recall, "f1": f1})
    micro_p, micro_r, micro_f1 = prf(total_tp, total_fp, total_fn)
    scored = [row for row in per_label if row["support"] > 0]
    summary = {
        "n": n,
        "accuracy": sum(g == p for g, p in zip(gold, pred)) / n if n else 0.0,  # exact match
        "jaccard": sum(jaccard(g, p) for g, p in zip(gold, pred)) / n if n else 0.0,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "macro_f1": sum(r["f1"] for r in scored) / len(scored) if scored else 0.0,
    }
    return summary, per_label


def confusions(gold: Iterable, pred: Iterable) -> Counter:
    """Counter of (gold, pred) pairs that differ."""
    return Counter((g, p) for g, p in zip(gold, pred) if g != p)


# ------------------------------------------------------------------- text
def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


def rouge_n_f1(reference: str, candidate: str, n: int = 1) -> float:
    def grams(words):
        return Counter(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    ref, cand = grams(tokens(reference)), grams(tokens(candidate))
    overlap = sum((ref & cand).values())
    return prf(overlap, sum(cand.values()) - overlap, sum(ref.values()) - overlap)[2]


def lcs_length(a: list[str], b: list[str]) -> int:
    previous = [0] * (len(b) + 1)
    for x in a:
        current = [0]
        for j, y in enumerate(b, start=1):
            current.append(previous[j - 1] + 1 if x == y else max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def rouge_l_f1(reference: str, candidate: str) -> float:
    ref, cand = tokens(reference), tokens(candidate)
    if not ref or not cand:
        return 0.0
    lcs = lcs_length(ref, cand)
    return prf(lcs, len(cand) - lcs, len(ref) - lcs)[2]
