# Data card: support routing

## Sources

| Dataset | Pinned at | Rows used | License (as recorded) |
| --- | --- | --- | --- |
| BANKING77 via `mteb/banking77` on the Hugging Face Hub | revision `18072d2685ea682290f7b8924d94c62acc19c0b2` | default config: 9,993 train, 3,076 test | MIT (dataset card); the original PolyAI release is CC BY 4.0 |
| ArBanking77, `github.com/SinaLab/ArBanking77` | commit `2e3a5639e254bc28828ed0af6d3059d64d3b97fc` | 21,559 train and 2,464 validation (MSA and Palestinian mixed); tests: MSA 3,574, Palestinian 3,807, Saudi 3,580, Moroccan 3,574, Tunisian 999 | MIT, according to the Hugging Face model card |

Both map to the same 77 intents (`src/carob_ml/labels.py`). English validation is a stratified
tenth of the English training rows (seed 20260303).

## Baseline (router trained 2026-09-10, TF-IDF characters and words, logistic regression)

| Test set | Rows | Accuracy | Macro-F1 | Queue accuracy |
| --- | --- | --- | --- | --- |
| English | 3,076 | 0.904 | 0.905 | 0.967 |
| MSA | 3,574 | 0.879 | 0.879 | 0.954 |
| Palestinian | 3,807 | 0.847 | 0.841 | 0.943 |
| Saudi | 3,580 | 0.721 | 0.715 | 0.887 |
| Moroccan | 3,574 | 0.607 | 0.597 | 0.809 |
| Tunisian | 999 | 0.457 | 0.198 | 0.653 |

## Known limits

- The Arabic training data is MSA and Palestinian only; the Gulf and Maghrebi results show it.
- Most Carob customers write Lebanese Arabic, which no test set covers.
- No per-variety confidence intervals yet; the Tunisian set is small.
