"""Scores the keyword theme tagger against your hand labels.
Run from the folder that contains labeling_sheet.csv and playstore_analyzer.py:
  python score_labels.py            # scores the tags that were in the sheet (original run)
  python score_labels.py --retag    # re-tags your 50 reviews with the CURRENT keywords in
                                    # playstore_analyzer.py and scores them against your labels
Outputs a printed summary and validation_results.csv.
"""
import re
import sys
import pandas as pd

CODES = ["BOOKING", "LOGIN", "CRASH", "TRACKING", "LATE", "DRIVER",
         "SAFETY", "ROUTING", "SUPPORT", "UI", "NOTIF", "ADDRESS", "CALLING", "RATING"]
KNOWN = set(CODES) | {"VAGUE", "NOTCOMPLAINT", "OTHER", "NONE"}
RETAG = "--retag" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
path = args[0] if args else "labeling_sheet.csv"
d = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=str).fillna("")
unknown = set()


def codes(cell):
    out = set()
    for p in re.split(r"[,;\s]+", str(cell).upper()):
        p = p.strip().split("-")[0]
        if not p:
            continue
        if p in KNOWN:
            out.add(p)
        else:
            unknown.add(p)
    return out


if RETAG:
    import playstore_analyzer as pa
    names = list(pa.COMPILED)
    d["script_tags"] = d["content"].map(
        lambda t: ",".join(c for n, c in zip(names, CODES) if pa.COMPILED[n][0].search(str(t))) or "NONE")
    print("\n*** RETAG MODE: tags recomputed with the keywords currently in playstore_analyzer.py ***")
    print("*** 'tagged_not_my_label' counts every tag that is not in your label (a strict proxy: ***")
    print("*** a correct secondary theme also counts against it). Keywords were tuned on these ***")
    print("*** same 50 reviews, so treat the coverage figure as optimistic. ***")

d["labels"] = d["my_label"].map(codes)
d["tags"] = d["script_tags"].map(codes)
d["wrong"] = d["wrong_tags"].map(codes).map(lambda s: s - {"NONE"})  # NONE in wrong_tags = "nothing wrong"
lab = d[d["labels"].map(len) > 0].copy()
print(f"\nRows in file: {len(d)} | labeled: {len(lab)} | unlabeled (ignored): {len(d) - len(lab)}")
if unknown:
    print("Unrecognized words ignored (check spelling):", sorted(unknown))

n = len(lab)
cnt = lambda c: int(lab["labels"].map(lambda s: c in s).sum())
specific = lab[lab["labels"].map(lambda s: bool(s & set(CODES)))]
hit = specific.apply(lambda r: bool(r["labels"] & r["tags"]), axis=1)
none_tag = int(lab["tags"].map(lambda s: "NONE" in s).sum())

print("\n== Overall (50 low-star reviews, read with the usual small-sample caution) ==")
print(f"Specific complaint (fits one of the themes): {len(specific)} ({100*len(specific)/n:.0f}%)")
print(f"VAGUE (no detail): {cnt('VAGUE')} | NOTCOMPLAINT: {cnt('NOTCOMPLAINT')} | OTHER (missing theme): {cnt('OTHER')}")
print(f"Script tagged nothing (NONE): {none_tag} ({100*none_tag/n:.0f}%)")
if len(specific):
    print(f"COVERAGE: for specific complaints, script tagged the right theme in {hit.sum()}/{len(specific)} ({100*hit.mean():.0f}%)")

print("\n== Your hand-label counts (a review can carry two labels) ==")
print(", ".join(f"{c}: {cnt(c)}" for c in sorted(CODES, key=cnt, reverse=True)))

rows = []
for c in CODES:
    tagged = lab[lab["tags"].map(lambda s: c in s)]
    if RETAG:
        wrong = int(tagged["labels"].map(lambda s: c not in s).sum())
    else:
        wrong = int(tagged["wrong"].map(lambda s: c in s).sum())
    labeled = lab[lab["labels"].map(lambda s: c in s)]
    found = int(labeled["tags"].map(lambda s: c in s).sum())
    prec = 1 - wrong / len(tagged) if len(tagged) else None
    rec = found / len(labeled) if len(labeled) else None
    if len(tagged) < 5:
        verdict = "too few tagged to judge"
    elif prec < 0.7:
        verdict = "FIX keywords (low precision)"
    elif rec is not None and len(labeled) >= 3 and rec < 0.5:
        verdict = "misses many (low recall)"
    else:
        verdict = "OK"
    rows.append({"theme": c, "times_tagged": len(tagged),
                 "tagged_not_my_label" if RETAG else "tagged_wrongly": wrong,
                 "precision": None if prec is None else round(prec, 2),
                 "my_label_count": len(labeled), "found_by_script": found,
                 "recall": None if rec is None else round(rec, 2), "verdict": verdict})
res = pd.DataFrame(rows).sort_values("times_tagged", ascending=False)
res.to_csv("validation_results.csv", index=False)
print("\n== Per theme (precision = tags that were right; recall = my labels the script found) ==")
print(res.to_string(index=False))

cut = lambda s: re.sub(r"\s+", " ", str(s))[:110]
missed = specific[~hit.values]
print(f"\n== Missed: specific theme you saw that the script did not tag ({len(missed)}) ==")
for _, r in missed.iterrows():
    print(f"#{r['id']} label={','.join(sorted(r['labels']))} tags={r['script_tags']} | {cut(r['content'])}")

if RETAG:
    extra = lab[lab.apply(lambda r: bool(r["tags"] - r["labels"] - {"NONE"}), axis=1)]
    print(f"\n== Extra tags not in your label ({len(extra)} reviews) - judge each: wrong, or a fine secondary theme? ==")
    for _, r in extra.iterrows():
        print(f"#{r['id']} extra={','.join(sorted(r['tags'] - r['labels'] - {'NONE'}))} | {cut(r['content'])}")
else:
    bad = lab[lab["wrong"].map(len) > 0]
    print(f"\n== Wrong tags you flagged ({len(bad)} reviews; 'NONE' entries ignored) ==")
    for _, r in bad.iterrows():
        print(f"#{r['id']} wrong={','.join(sorted(r['wrong']))} | {cut(r['content'])}")

oth = lab[lab["labels"].map(lambda s: "OTHER" in s)]
print(f"\n== Your OTHER notes ({len(oth)}) - possible missing themes ==")
for _, r in oth.iterrows():
    print(f"#{r['id']} {r['my_label']} | {cut(r['content'])}")
print("\nSaved: validation_results.csv")