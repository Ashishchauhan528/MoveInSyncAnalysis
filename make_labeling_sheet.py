"""Turns out/<latest>/validation_sample.csv into labeling_sheet.csv (easy to fill in Excel/Sheets).
Run from the same folder where you ran playstore_analyzer.py:  python make_labeling_sheet.py
"""
import glob
import pandas as pd

f = sorted(glob.glob("out/*/validation_sample.csv"))[-1]
d = pd.read_csv(f)
themes = [c for c in d.columns if c not in ("content", "score")]
codes = dict(zip(themes, ["BOOKING", "LOGIN", "CRASH", "TRACKING", "LATE", "DRIVER",
                          "SAFETY", "ROUTING", "SUPPORT", "UI", "NOTIF", "ADDRESS", "CALLING", "RATING"]))
d["script_tags"] = d[themes].apply(
    lambda r: ",".join(codes[t] for t in themes if r[t]) or "NONE", axis=1)
sheet = pd.DataFrame({"id": range(1, len(d) + 1), "score": d["score"],
                      "content": d["content"], "my_label": "", "wrong_tags": "",
                      "script_tags": d["script_tags"]})
sheet.to_csv("labeling_sheet.csv", index=False, encoding="utf-8-sig")
print(f"{len(sheet)} rows from {f} written to labeling_sheet.csv")