# Measured LOL-v1 results

Official 15-image test partition; full RGB [0,1], no reference exposure adjustment, CPU inference, 1024px inference tile limit (all test images fit whole-frame).

| Method | PSNR (higher) | SSIM (higher) | LPIPS (lower) | NIQE (generally lower) |
|---|---:|---:|---:|---:|
| classical | 13.5286 | 0.5166 | 0.3678 | 7.8276 |
| deep | 25.1553 | 0.8441 | 0.1314 | 3.4792 |
| hybrid | 19.1588 | 0.7847 | 0.1799 | 4.3247 |

All four scores have 15 valid measurements per method. Scores are read from `outputs/LOL-v1-final-benchmark/report.json`; they are not seeded UI values.

Retinexformer outperformed the current rule-based hybrid on this test set. The hybrid is not claimed to be automatically superior. Controller rules were not tuned against these test references.

The complete nine-variant ablation study contains 135 measured rows in `outputs/LOL-v1-final-ablations/report.json`, with per-image diagnostics, candidate decisions, CSV exports, images, and SVG plots.

An exploratory one-epoch fine-tuning run used 437 images and 48 development images split from the official training partition. The original checkpoint may already have seen these development images during its upstream pretraining; this split is not an independent unseen pretraining evaluation. The untouched 15-image test partition was not used for optimization.

## Exploratory adaptation test comparison

| Metric | Original pretrained | One-epoch adapted | Change |
|---|---:|---:|---:|
| psnr | 25.1553 | 21.5054 | -3.6499 |
| ssim | 0.8441 | 0.8132 | -0.0309 |
| lpips | 0.1314 | 0.1719 | +0.0405 |
| niqe | 3.4792 | 3.4342 | -0.0451 |

Adaptation degraded the reference metrics despite a slightly lower NIQE. The application keeps the original pretrained checkpoint; NIQE alone does not justify promotion. These results establish behavior on LOL-v1, not universal cross-dataset quality.

Source: https://daooshee.github.io/BMVC2018website/ . Dataset archive SHA256: `47d85314b7927470cd48c97e5c1d6c896a56d6217c8e508d0736aff2d91aadcc`.
