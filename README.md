# MoveInSync Play Store ratings: why are they lower than they should be?

Answers "How are our Play Store ratings?" in one command and shows which app problems drive 1-2 star reviews.

**Recommendation document:** (https://drive.google.com/file/d/146mdICKLpEU03mdQInPhrXlUI_TPwKSl/view?usp=sharing) and copy of it is
in docs/ folder in the pdf form.

## Headline findings
- Official rating is 4.64 (about 114,900 ratings). About 70% of the 0.36 gap to 5.0 is 1-star ratings.
- Written reviews skew about 4x more negative than all ratings, so they are used only to explain *why* people give 1-2 stars.
- Top themes in 1,413 low-star reviews: crash/slow 17.9%, login/OTP 15.5%, booking/scheduling 11.0%.
- Fix first: stability and speed, then booking flow, then login/OTP. This week: test the SOS button and reply to 1-2 star reviews (4.8% get one today).
- Late cabs, routing and helpdesk issues belong to operations.
- Keyword mentions are not proven causes; see the limits section of the document.

## Run it
```
pip install -r requirements.txt
python playstore_analyzer.py                 # scrape 5,000 latest reviews, tag, report
python playstore_analyzer.py --from-csv out/<date>/reviews.csv   # re-tag saved reviews
python final_analysis.py                     # deeper tables (trends, sub-problems, replies)
```
Outputs go to `out/<date>/` (report.md, charts, validation sample) and one row is appended to `out/history.csv` per run, so the trend builds up.

## Validation
`make_labeling_sheet.py` -> label 50 reviews by hand -> `score_labels.py [--retag]` (coverage, precision, recall per theme). `spot_check.py` prints 10 random reviews per theme for quick precision checks.

## Limits
Only written reviews are available; themes are keyword-based and tuned on the same 50 labeled reviews; no device or OS data. Raw review CSVs contain user names and are not committed.