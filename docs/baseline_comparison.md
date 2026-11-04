# NLP baseline comparison (measured, held-out test split)

Dataset: 960 labelled pairs from `data/pairs.csv` (SYNTHETIC, see data_report.md).
Split: 70/15/15 grouped by incident (an incident's two variants never land in
two splits; TF-IDF vocabulary fit on train only). Threshold chosen on the
validation split, applied to the test split.

| method | val AUC | test AUC | test precision | test recall | test F1 | test acc | threshold |
|---|---|---|---|---|---|---|---|
| TF-IDF + cosine | 0.9893 | 0.992 | 0.907 | 0.9512 | 0.9286 | 0.9586 | 0.6021 |
| SentenceTransformer + cosine | 0.9969 | 0.9979 | 0.973 | 0.878 | 0.9231 | 0.9586 | 0.854 |

Test confusion matrices:
- TF-IDF: TP=39 FP=4 FN=2 TN=100
- Sentence: TP=36 FP=1 FN=5 TN=103

**Reading:** cosine similarity alone (either representation) is the *baseline*
approach currently shipped. The supervised classifier in `train_dedup.py`
combines these similarities with lexical features and is compared against
these numbers in MODEL_SELECTION.md.
