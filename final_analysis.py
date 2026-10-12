"""Final analysis on the tagged reviews. Run from the folder with playstore_analyzer.py:
    python final_analysis.py
Reads out/<latest>/reviews_tagged.csv (re-create it first with:
    python playstore_analyzer.py --from-csv out\\<date>\\reviews.csv ).
Prints compact tables. All counts are keyword-based mentions among 1-2 star reviews (approximate).
"""
import glob
import math
import re
import pandas as pd
import playstore_analyzer as pa

f = sorted(glob.glob("out/*/reviews_tagged.csv"))[-1]
df = pd.read_csv(f, parse_dates=["at"])
df["content"] = df["content"].fillna("").astype(str)
themes = [t for t in pa.COMPILED if t in df.columns]
low = df[df["score"] <= 2].copy()
n_low = len(low)
print(f"File: {f} | reviews: {len(df)} | low-star (1-2): {n_low} ({100 * n_low / len(df):.1f}%)")


def T(prefix):
    col = [t for t in themes if t.startswith(prefix)]
    return low[low[col[0]].astype(bool)] if col else low.iloc[0:0]


def count(label, rx, base):
    n = len(base)
    c = int(base["content"].str.contains(rx, case=False, regex=True).sum()) if n else 0
    print(f"  {label:50s} {c:4d}  ({(100 * c / n if n else 0):.0f}% of {n})")


# ---------------------------------------------------------------- A
print("\n== A. Theme share of low-star reviews (mentions; a review can have several themes) ==")
rows = []
for t in themes:
    c = int(low[t].sum())
    p = c / n_low
    rows.append((t, c, 100 * p, 196 * math.sqrt(p * (1 - p) / n_low)))
for t, c, p, h in sorted(rows, key=lambda r: -r[1]):
    print(f"{t:36s} {c:5d}  {p:5.1f}%  (+/-{h:.1f})")
print("Differences smaller than the +/- values are ties.")

# ---------------------------------------------------------------- B
cut = df["at"].max() - pd.Timedelta(days=90)
rec, old = low[low["at"] >= cut], low[low["at"] < cut]
print(f"\n== B. Last 90 days ({len(rec)} low-star) vs earlier ({len(old)}): themes that moved by more than noise ==")
moved = False
for t in themes:
    p1, p2 = rec[t].mean(), old[t].mean()
    se = math.sqrt(p1 * (1 - p1) / len(rec) + p2 * (1 - p2) / len(old))
    if se and abs(p1 - p2) / se >= 2:
        moved = True
        print(f"  {t}: {100 * p1:.1f}% now vs {100 * p2:.1f}% earlier")
if not moved:
    print("  None. No theme shifted beyond noise.")

# ---------------------------------------------------------------- C
m = df.groupby("month")["score"].agg(["mean", "count"])
m = m[m["count"] >= 150]
print("\n== C. The 5 weakest months (>=150 reviews): what was different? ==")
print(f"(overall mean {df['score'].mean():.2f}; 'pp' = percentage points above that theme's usual share in other months)")
for mo, r in m.sort_values("mean").head(5).iterrows():
    cur, rest = low[low["month"] == mo], low[low["month"] != mo]
    diffs = sorted(((100 * (cur[t].mean() - rest[t].mean()), t) for t in themes), reverse=True)[:3]
    ver = df[df["month"] == mo]["reviewCreatedVersion"].value_counts().head(2)
    print(f"{mo}: avg {r['mean']:.2f} (n={int(r['count'])}, low-star n={len(cur)})")
    print("    themes above usual: " + "; ".join(f"{t} +{d:.0f}pp" for d, t in diffs))
    print("    most common app versions: " + ", ".join(f"{v} ({c})" for v, c in ver.items()))

# ---------------------------------------------------------------- D
print("\n== D. Specific problems inside the top themes (low-star reviews; keyword counts, approximate) ==")
L = T("Login")
print(f"LOGIN / OTP ({len(L)} reviews)")
count("OTP not received / not accepted / delayed",
      r"(?:not|never|n['’]t|no|unable|cannot|didn|doesn|delay|late|fail|invalid|wrong|expire)\W+(?:\w+\W+){0,6}otp"
      r"|otp\W+(?:\w+\W+){0,6}(?:not|never|n['’]t|delay|late|fail|invalid|wrong|expire|come|receiv)", L)
count("asked to log in / enter OTP again and again",
      r"(?:every|each) ?(?:time|minute)|again and again|repeated|keeps? (?:asking|logging|signing)|automatic\w* (?:log|sign)"
      r"|logs? ?out|logged out|sign(?:s|ed)? out|few minutes|5 ?min", L)
count("asked to register / reinstall again", r"regist\w+ again|re-?regist|re-?install|uninstall|asking (?:me )?to regist", L)
count("cannot log in at all",
      r"(?:unable|not able|cannot|can['’]?t|couldn['’]?t) (?:to )?(?:log ?in|sign ?in|access)|login (?:issue|problem|fail|error)", L)

C = T("App crash")
print(f"\nAPP CRASH / MALFUNCTION ({len(C)} reviews)")
count("crashes / closes by itself / will not open",
      r"crash|force clos|clos\w+ (?:automatically|itself|by itself)|open and clos|not open|won['’]?t open|keeps? (?:closing|stopping)|stopped working", C)
count("blank / white / black screen", r"(?:blank|white|black) screen", C)
count("slow / laggy / long loading", r"slow|laggy|\blag|loading|takes? (?:too |so |very )?(?:much|long)|time to load", C)
count("started after an update / new version", r"(?:after|since|latest|new|recent|last) (?:the )?(?:update|version|upgrade)|upgrade", C)
count("QR code / scan problems", r"\bqr\b|scan", C)
count("review names a phone brand or Android/iOS",
      r"android|pixel|samsung|oneplus|iphone|\bios\b|oppo|vivo|redmi|realme|xiaomi|motorola|nothing phone|poco", C)

B = T("Booking")
print(f"\nBOOKING / SCHEDULING ({len(B)} reviews)")
count("cannot book / button disabled / no seat",
      r"(?:unable|not able|cannot|can['’]?t|couldn['’]?t|fail\w*)\W+(?:\w+\W+){0,4}(?:book|schedul)|book now|disabled"
      r"|no (?:seat|cab|vehicle|shuttle)s? (?:available|found)|seats? not available", B)
count("confirmed booking auto-cancelled / waitlist / no-show",
      r"auto.?cancel|cancel\w* (?:automatically|my|the)|no.?show|waitlist|wait list|marked (?:as )?(?:absent|no)", B)
count("date / time / schedule display or logic", r"\bdates?\b|am.?pm|24.?h|calendar|previous schedule|schedule", B)
count("nodal point / pickup point issues", r"nodal|pick.?up point|boarding point", B)
count("parking or desk booking", r"parking|\bdesk\b", B)

K = T("Live tracking")
print(f"\nLIVE TRACKING / ETA ({len(K)} reviews)")
count("location not updating / stuck / delayed", r"not updat|doesn['’]?t update|no update|never update|stuck|same place|delay|lag|real.?time|late", K)
count("ETA / pickup time inaccurate", r"\beta\b|estimated|accura|pickup time|pick.?up time|timing", K)
count("map problems (zoom, fluctuating, hangs)", r"\bmaps?\b|zoom|fluctuat", K)
count("worse after an upgrade / feature removed", r"(?:before|after|since|earlier) (?:the )?(?:update|upgrade|version)|no longer|removed|not available now", K)

Cc = T("In-app calling")
print(f"\nIN-APP CALLING ({len(Cc)} reviews)")
count("cannot call / contact driver or employee from the app",
      r"(?:not able|unable|can['’]?t|cannot|no option|no way) (?:to )?(?:call|contact|reach|text|message|chat)", Cc)
count("alternate / personal number issues", r"alternat\w+ number|alternative number|personal number|mobile number", Cc)
count("microphone permission", r"microphone|\bmic\b|permission", Cc)

S = low[low["content"].str.contains(r"help ?desk|helpline|transport (?:team|desk)|customer care|call ?cent|support (?:team|staff)", case=False, regex=True)]
print(f"\nHELPDESK / TRANSPORT TEAM mentioned ({len(S)} reviews)")
count("unreachable / not responding / no solution",
      r"(?:not|never|no)\W+(?:\w+\W+){0,4}(?:pick|answer|respon|reach|connect|reply|call back|solution|help)|disconnect|switched off|unreachable", S)
count("rude / unhelpful staff", r"rude|unhelpful|unprofessional|laugh|not (?:very )?helpful|attitude|\btone\b", S)

print("\nOTHER SIGNALS (all low-star reviews)")
count("dark mode requests", r"dark mode", low)
count("no-show disputes (marked absent / no-show)", r"no.?show|marked (?:as )?absent", low)
count("mentions a competitor or another app", r"efmfm|rapido|uber|\bola\b|competitor|other app|better app", low)
count("safety-related words (women, harass, unsafe, accident...)", r"unsafe|harass|women|girl|female|accident|safety|panic|\bsos\b", low)

# ---------------------------------------------------------------- E
print("\n== E. Developer replies ==")
rep = df[df["replyContent"].notna()]
low_rep = low[low["replyContent"].notna()]
print(f"Replied to {len(rep)} of {len(df)} reviews ({100 * len(rep) / len(df):.1f}%); to {len(low_rep)} of {len(low)} low-star ({100 * len(low_rep) / len(low):.1f}%)")
if len(rep):
    uniq = rep["replyContent"].astype(str).str.slice(0, 80).nunique()
    days = (pd.to_datetime(rep["repliedAt"], errors="coerce") - rep["at"]).dt.total_seconds() / 86400
    print(f"Distinct reply openings (first 80 chars): {uniq} of {len(rep)} replies | median days to reply: {days.median():.1f}")
    for txt in rep["replyContent"].astype(str).drop_duplicates().head(2):
        print("  e.g. " + re.sub(r"\s+", " ", txt)[:170])

# ---------------------------------------------------------------- F
sf = [t for t in themes if t.startswith("Safety")]
if sf:
    s = low[low[sf[0]].astype(bool)]
    print(f"\n== F. All {len(s)} low-star reviews tagged Safety (severity matters more than count) ==")
    for i, (_, r) in enumerate(s.iterrows(), 1):
        print(f"{i}. [{int(r['score'])}*] " + re.sub(r"\s+", " ", r["content"])[:230])