# -*- coding: utf-8 -*-
"""Generate the tiny demo dataset (demo/demo_data.json).

Synthetic LLM-agent trajectory toy corpus: 40 failing + 10 succeeding
trajectories over 8 command-family symbols, with two planted failure chains:
  [2, 5]  (edit -> git_push)      frequent in failing, rare in succeeding
  [3, 2, 5] (search -> edit -> git_push)  a longer order-sensitive chain
Run once to (re)create the JSON; run_demo.py consumes it.
"""
import json
import os
import random

random.seed(42)

SYMBOLS = {
    "1": "bash", "2": "edit", "3": "search", "4": "test",
    "5": "git_push", "6": "submit", "7": "retry", "8": "browse",
}

# Signature alphabet delivered by the (toy) itemset layer: the coupling
# restricts sequence-layer search to symbols appearing in delivered signatures.
SIGNATURES = [[2, 5], [3, 2], [6]]

POOL = [1, 2, 3, 4, 5, 6, 7, 8]


def make_failing():
    seq = []
    # 70% contain the planted chain edit -> git_push (order-sensitive)
    if random.random() < 0.70:
        seq += [2, 5]
    # 35% contain the longer chain search -> edit -> git_push
    if random.random() < 0.35:
        seq = [3] + seq if seq[:1] != [3] else seq
        if seq[-1:] != [5]:
            seq.append(5)
    # filler actions
    while len(seq) < random.randint(5, 9):
        s = random.choice(POOL)
        seq.append(s)
        if random.random() < 0.2:
            seq.append(s)  # occasional repeated step
    return seq


def make_succeeding():
    seq = []
    # the same symbols appear, but the failure ORDER is broken:
    # git_push before edit, and search rarely adjacent to the pair
    banned_5 = False  # once 'edit' appears, 'git_push' must never follow
    while len(seq) < random.randint(5, 9):
        pick = random.choice(POOL)
        if pick == 2:
            banned_5 = True
        if banned_5 and pick == 5:
            pick = 1
        seq.append(pick)
    return seq


data = {
    "description": (
        "Toy LLM-agent trajectory corpus for the one-click demo of the "
        "two-layer coupling (Section 4.2). Symbols are command families; "
        "'failing' trajectories end in task failure, 'succeeding' in success."
    ),
    "symbols": SYMBOLS,
    "signatures": SIGNATURES,
    "failing": [make_failing() for _ in range(40)],
    "succeeding": [make_succeeding() for _ in range(10)],
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
print("wrote", out)
