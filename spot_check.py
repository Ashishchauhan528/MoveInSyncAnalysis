"""Held-out spot check of the keyword tagger (reviews you did NOT label).
Prints 10 random 1-2 star reviews for each of the top themes. For each theme, count how many
of the 10 are REALLY about it (the theme is the actual complaint, not an incidental word).
Run from the folder with playstore_analyzer.py:
  python spot_check.py        # top 3 themes
  python spot_check.py 5      # top 5 themes
  python spot_check.py BOOKING UI DRIVER   # chosen themes by code
"""
import glob
import os
import re
import sys
import pandas as pd
import playstore_analyzer as pa

CODES = ["BOOKING", "LOGIN", "CRASH", "TRACKING", "LATE", "DRIVER", "SAFETY", "ROUTING",
         "SUPPORT", "UI", "NOTIF", "ADDRESS", "CALLING", "RATING"]
args = [a.upper() for a in sys.argv[1:]]
wanted = [a for a in args if a in CODES]
top_n = next((int(a) for a in args if a.isdigit()), 3)
norm = lambda s: re.sub(r"\s+", " ", str(s)).strip().lower()
f = sorted(glob.glob("out/*/reviews_tagged.csv"))[-1]
df = pd.read_csv(f)
low = df[df["score"] <= 2].copy()
low["_n"] = low["content"].map(norm)
excluded = 0
if os.path.exists("labeling_sheet.csv"):
    sheet = pd.read_csv("labeling_sheet.csv", sep=None, engine="python", encoding="utf-8-sig", dtype=str)
    done = set(sheet["content"].fillna("").map(norm))
    mask = low["_n"].isin(done)
    excluded = int(mask.sum())
    low = low[~mask]
themes = [t for t in pa.COMPILED if t in low.columns]
counts = low[themes].sum().sort_values(ascending=False)
print(f"File: {f}")
print(f"Low-star reviews available: {len(low)} (excluded {excluded} that match your labeled sheet)")
print("Low-star mentions per theme: " + ", ".join(f"{t}: {int(n)}" for t, n in counts.items()))
by_code = dict(zip(pa.COMPILED, CODES))
chosen = ([t for c in wanted for t, cc in by_code.items() if cc == c and t in low.columns]
          if wanted else list(counts.index[:top_n]))
for t in chosen:
    sub = low[low[t].astype(bool)]
    s = sub.sample(min(10, len(sub)), random_state=7)
    print(f"\n=== {t} ({int(counts[t])} low-star mentions): how many of these {len(s)} are REALLY about it? ===")
    for i, (_, r) in enumerate(s.iterrows(), 1):
        print(f"{i}. [{int(r['score'])}*] " + re.sub(r"\s+", " ", str(r["content"]))[:220])