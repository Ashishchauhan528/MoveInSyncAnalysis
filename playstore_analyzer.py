#!/usr/bin/env python3
"""
Play Store rating analyzer (repeatable).
Answers: "How are our Play Store ratings, and why?"

Run:   python playstore_analyzer.py                       # scrape + analyze + report
       python playstore_analyzer.py --max 8000            # more reviews
       python playstore_analyzer.py --from-csv reviews.csv  # re-analyze without scraping
       python playstore_analyzer.py --app com.other.app   # another app (e.g. driver app)

Install: pip install google-play-scraper pandas matplotlib
Output : out/<date>/reviews.csv, report.md, charts, and out/history.csv (one row per run)
"""
import argparse, os, re, time, datetime as dt
import warnings
warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression")
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_APP = "com.moveinsync.ets"  # MoveInSync employee app (verify on the Play Store URL)

# theme -> (regex, owner). Keyword rules = free and transparent. Tune after reading real reviews.
THEMES = {
    "Booking fails / no cab or seat": (r"(unable|not (been )?able|cannot|can't|cant|fail(ed|s)?|error|issue|problem).{0,30}(book|schedul)|(book|schedul)\w*.{0,30}(fail|error|not (work|show)|issue|problem|option|inconvenien)|\bbook(ing|ed|s)?\b|\bschedul|\broster|no (cab|vehicle|seat|shuttle)s? (available|found)|seats? not available|auto.?cancel|cancel(l)?ed (my )?(booking|trip|ride|cab)|date range|select the date|pick.?up (and|&) drop", "Product + Eng"),
    "Login / OTP / registration": (r"login|log in|logged (in|out)|log ?out|sign in|signin|sign(ed)? out|\botps?\b|verification code|password|register|registration|can.?t access|\baccount\b", "Engineering"),
    "App crash / bug / slow": (r"crash|\bhang|\bfreez|\bstuck|\bbugs?\b|glitch|not working|doesn.?t work|not open|force close|\bslow|\blag(gy|ging|s)?\b|\bload|not responding|unstable|stability|black screen|white screen|blank screen|error", "Engineering"),
    "Live tracking / GPS / ETA": (r"\btrack|\bgps\b|\bmaps?\b|\blive\b|\beta\b|real.?time|where is (my )?(cab|vehicle|bus)|(cab|vehicle|driver|bus|shuttle)'?s? location|location (update|updat|not (updat|show|work|accurate)|is (wrong|incorrect|not))|(wrong|incorrect) locations?|location (error|issue)", "Engineering"),
    "Late / no-show cab": (r"\blate\b|delay|waiting|wait for|not arrive|didn.?t (come|arrive|show)|did not (come|arrive|show)|no.?show|never (came|arrived|showed)|missed (my|the)|too long|not (on|in) time|unpunctual", "Operations"),
    "Driver behaviour": (r"driver|rude|misbehav|behaviou?r|\brash\b|not picking|not answering|refus|harass", "Operations"),
    "Safety / women's safety": (r"\bsafe\b|safety|unsafe|women|\bsos\b|panic|escort|accident", "Ops + Product"),
    "Routing / pickup time changes": (r"\broute|routing|detour|pick.?up time|resched|shuffl|reassign|different cab|changed (the )?(time|cab)|last minute|sequenc|clubb", "Ops / Routing"),
    "Support / complaint not resolved": (r"support|customer care|helpdesk|help desk|no response|complaint|escalat|ticket|nobody|not resolved|no action|no reply|no feedback|reported (the )?(issue|problem)s?|no answer|never (get|got|receive[d]?) (an? )?(answer|reply|response)|unresponsive|not (replied|responded|answered)", "Ops / Support"),
    "UI/UX & forced updates": (r"\bui\b|\bux\b|interface|confusing|complicated|design|user.?friendly|(new|latest|recent) (update|version)|(after|before) (the )?update|old version|previous version|force.{0,10}update|inconvenien|dark mode|no option|difficult|cumbersome|hard to (use|find|understand)", "Product"),
    "Notifications / SMS": (r"notification|notify|alert|\bsms\b", "Engineering"),
    "Address / home location": (r"address|home location|pin ?code|change location|update location", "Product"),
    "In-app calling / mic permission": (r"\bcall(s|ed|ing)?\b|microphone|\bmic\b|switched off|\bbusy\b|disconnect", "Engineering"),
    "Trip rating / feedback feature": (r"\brat(e|ed|ing|ings)\b", "Product"),
}
COMPILED = {k: (re.compile(v[0], re.I), v[1]) for k, v in THEMES.items()}


def scrape(app_id, lang, country, max_reviews):
    from google_play_scraper import reviews, Sort
    out, token = [], None
    while len(out) < max_reviews:
        batch, token = reviews(app_id, lang=lang, country=country, sort=Sort.NEWEST,
                               count=200, continuation_token=token)
        if not batch:
            break
        out += batch
        print(f"  fetched {len(out)} reviews...", end="\r")
        if token is None:
            break
        time.sleep(1)
    print()
    df = pd.DataFrame(out)
    keep = ["reviewId", "userName", "content", "score", "thumbsUpCount", "reviewCreatedVersion", "at", "replyContent", "repliedAt"]
    return df[[c for c in keep if c in df.columns]]


def tag(df):
    text = df["content"].fillna("").astype(str)
    for name, (rx, _) in COMPILED.items():
        df[name] = text.str.contains(rx)
    df["no_theme"] = ~df[list(THEMES)].any(axis=1)
    return df


def theme_table(df):
    low = df[df.score <= 2]
    base = df.score.mean()
    rows = []
    for name, (_, owner) in COMPILED.items():
        sub = df[df[name]]
        low_sub = low[low[name]]
        # what-if: if every <=2-star review about this theme had been 4 stars
        lifted = df.score.copy()
        lifted[df[name] & (df.score <= 2)] = 4
        rows.append({
            "Theme": name, "Owner": owner,
            "Reviews": len(sub),
            "% of all": round(100 * len(sub) / len(df), 1),
            "Low-star (1-2) reviews": len(low_sub),
            "% of low-star": round(100 * len(low_sub) / max(len(low), 1), 1),
            "Avg stars when mentioned": round(sub.score.mean(), 2) if len(sub) else None,
            "Rating lift if fixed (est.)": round(lifted.mean() - base, 3),
        })
    t = pd.DataFrame(rows).sort_values("Rating lift if fixed (est.)", ascending=False)
    return t


def examples(df, theme, n=2):
    sub = df[(df[theme]) & (df.score <= 2)].sort_values("thumbsUpCount", ascending=False).head(n)
    return [re.sub(r"\s+", " ", str(c))[:170] for c in sub.content]


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=DEFAULT_APP)
    ap.add_argument("--max", type=int, default=5000)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="in")
    ap.add_argument("--from-csv")
    ap.add_argument("--recent-days", type=int, default=90)
    a = ap.parse_args()

    today = dt.date.today().isoformat()
    outdir = os.path.join("out", today)
    os.makedirs(outdir, exist_ok=True)

    official = {}
    if a.from_csv:
        df = pd.read_csv(a.from_csv, parse_dates=["at"])
    else:
        print(f"Scraping {a.app} ...")
        df = scrape(a.app, a.lang, a.country, a.max)
        try:
            from google_play_scraper import app as app_info
            info = app_info(a.app, lang=a.lang, country=a.country)
            official = {"title": info["title"], "score": info["score"], "ratings": info["ratings"],
                        "histogram": info["histogram"], "version": info["version"]}
        except Exception as e:
            print("Could not fetch official app info:", e)
        df.to_csv(os.path.join(outdir, "reviews.csv"), index=False)

    df["at"] = pd.to_datetime(df["at"])
    df = tag(df)
    df["month"] = df["at"].dt.to_period("M").astype(str)

    # ---- headline numbers
    n = len(df)
    avg = df.score.mean()
    cutoff = df["at"].max() - pd.Timedelta(days=a.recent_days)
    recent = df[df["at"] >= cutoff]
    prev = df[(df["at"] < cutoff) & (df["at"] >= cutoff - pd.Timedelta(days=a.recent_days))]
    low_share = 100 * (df.score <= 2).mean()
    replied = df["replyContent"].notna().mean() * 100 if "replyContent" in df else 0
    dist = df.score.value_counts().sort_index()

    # ---- trends
    monthly = df.groupby("month").score.agg(["mean", "count"]).round(2)
    ver = df.groupby("reviewCreatedVersion").score.agg(["mean", "count"])
    ver = ver[ver["count"] >= max(30, n // 100)].round(2)
    ver = ver.sort_values("mean").head(10).reset_index().rename(columns={"reviewCreatedVersion": "App version", "mean": "Avg stars", "count": "Reviews"})

    themes = theme_table(df)
    themes_recent = theme_table(recent) if len(recent) > 50 else None

    # ---- charts
    fig, ax = plt.subplots(figsize=(9, 4))
    monthly["mean"].plot(ax=ax, marker="o")
    ax.set_title("Average stars per month (sampled reviews)"); ax.set_ylabel("stars"); ax.set_ylim(1, 5); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "rating_by_month.png"), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    t = themes.sort_values("% of low-star")
    ax.barh(t["Theme"], t["% of low-star"]); ax.set_xlabel("% of 1-2 star reviews mentioning theme")
    ax.set_title("What drives low ratings"); fig.tight_layout()
    fig.savefig(os.path.join(outdir, "themes_low_star.png"), dpi=130); plt.close(fig)

    # ---- history (so "how are our ratings?" can be answered over time)
    hist_path = os.path.join("out", "history.csv")
    row = pd.DataFrame([{"date": today, "app": a.app, "official_score": official.get("score"),
                         "sample_n": n, "sample_avg": round(avg, 3),
                         f"avg_last_{a.recent_days}d": round(recent.score.mean(), 3) if len(recent) else None,
                         "pct_1_2_star": round(low_share, 1)}])
    row.to_csv(hist_path, mode="a", header=not os.path.exists(hist_path), index=False)

    # ---- report
    L = []
    L.append(f"# Play Store rating report - {today}\n")
    L.append(f"App: `{a.app}` | Reviews analysed: {n} ({df['at'].min().date()} to {df['at'].max().date()})\n")
    if official:
        L.append(f"**Official Play Store score:** {official['score']:.2f} from {official['ratings']:,} ratings (current version {official['version']}). "
                 f"Histogram 1-5 stars: {official['histogram']}\n")
    L.append("## Headline\n")
    L.append(f"- Sample average: **{avg:.2f}** stars; **{low_share:.0f}%** of reviews are 1-2 stars.")
    if len(recent):
        L.append(f"- Last {a.recent_days} days: **{recent.score.mean():.2f}** ({len(recent)} reviews)"
                 + (f" vs previous {a.recent_days} days: {prev.score.mean():.2f}" if len(prev) else "") + ".")
    L.append(f"- Developer reply rate: **{replied:.0f}%** of reviews.")
    L.append(f"- Star distribution: " + ", ".join(f"{k}*: {v}" for k, v in dist.items()) + "\n")
    L.append("## Why the rating is low: themes ranked by estimated rating lift if fixed\n")
    L.append("`Rating lift` = how much the average would rise if every 1-2 star review about that theme had been 4 stars. A reviewer can mention several themes, so lifts overlap and are not additive.\n")
    L.append(md_table(themes) + "\n")
    L.append("## Example low-star reviews per top theme\n")
    for th in themes["Theme"].head(6):
        L.append(f"**{th}**")
        for e in examples(df, th):
            L.append(f"- \"{e}\"")
        L.append("")
    if themes_recent is not None:
        L.append(f"## Same table for the last {a.recent_days} days only (what is hurting NOW)\n")
        L.append(md_table(themes_recent) + "\n")
    L.append("## Worst app versions (min review count applied)\n")
    L.append(md_table(ver) + "\n")
    L.append("## Monthly trend\n")
    L.append(md_table(monthly.reset_index().rename(columns={"month": "Month", "mean": "Avg stars", "count": "Reviews"})) + "\n")
    L.append("![trend](rating_by_month.png)\n\n![themes](themes_low_star.png)\n")
    L.append("## Method and limits\n- Reviews pulled with google-play-scraper (newest first). Themes are tagged with keyword rules (multi-label); validate on a manual sample and tune `THEMES`.\n- Reviews are self-selected and the sample may differ from the official all-time score.\n- `no_theme` reviews (mostly short praise or vague text) are not counted in any theme.\n")
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    # tagged file for manual validation (50 random low-star reviews)
    df[df.score <= 2].sample(min(50, (df.score <= 2).sum()), random_state=1)[["content", "score"] + list(THEMES)].to_csv(
        os.path.join(outdir, "validation_sample.csv"), index=False)
    df.to_csv(os.path.join(outdir, "reviews_tagged.csv"), index=False)
    print(f"Done. Open {outdir}/report.md")


if __name__ == "__main__":
    main()