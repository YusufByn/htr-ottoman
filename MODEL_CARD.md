---
summary: Ottoman Turkish handwritten naskh, fine-tuned on MAKHZAN (v0.1.0)
authors:
  - name: Yusuf Buyukaydin
license: CC-BY-NC-SA-4.0
software_name: kraken
software_hints:
  - kind=safetensors
  - version>=5.0.0
  - seg_type=baselines
  - one_channel_mode=L
  - legacy_polygons=True
language:
  - ota
script:
  - Arab
model_type:
  - recognition
tags:
  - kraken_pytorch
  - htr
  - ottoman turkish
  - naskh
  - manuscripts
datasets:
  - https://doi.org/10.5281/zenodo.19861912
base_model:
  - https://doi.org/10.5281/zenodo.7050342
metrics:
  cer: 26.33
  cer_validation: 16.32
---
# Ottoman Turkish handwritten naskh, fine-tuned on MAKHZAN (v0.1.0)

A kraken text recognition model for **Ottoman Turkish manuscripts in naskh**, obtained by fine-tuning the OpenITI printed Ottoman base model on the Ottoman manuscripts of OpenITI MAKHZAN. It is a research model (v0.1.0): it has been evaluated once on a held-out internal test set, and never on data from another source.

## Model

- **DOI**: [10.5281/zenodo.23502722](https://doi.org/10.5281/zenodo.23502722) (Zenodo).
- **File**: `ota_naskh_makhzan_v0.1.0.safetensors`, SHA-256 `4d96d85f2f93fd9008f4d48bbcfbfc87aefe0c698ce5cf1dd3310e761ecd022e`.
- **Base model**: *Printed Ottoman Base Model Trained on the OpenITI Corpus* (B. Kiessling, 2022, CC0), DOI [10.5281/zenodo.7050342](https://doi.org/10.5281/zenodo.7050342). Input lines of 120 px, grayscale, baseline segmentation, NFD text; codec of 196 characters, kept unchanged.
- **Fine-tuning**: kraken 7.1.1, Adam, constant learning rate 1e-4, batch size 16, seed 42, early stopping on validation character accuracy after 5 epochs without improvement (91 epochs run); the model is the best epoch (86). Text settings of the base model: NFD, whitespace normalisation, BiDi reordering.
- **Line extraction**: the model was trained and evaluated with kraken's *legacy* polygon extractor. kraken 7.1.1 drops this flag when converting a checkpoint; in this file the flag is set back to `legacy_polygons: true` in the header metadata. **The weights are byte-identical to the evaluated model**; only this header field differs. Loaded by kraken without any override, the file reproduces the evaluated validation predictions byte for byte (412 lines, CER 16.32 %).

## Data

All data come from **OpenITI MAKHZAN** 2026.1.2 (CC BY-NC-SA 4.0), DOI [10.5281/zenodo.19861912](https://doi.org/10.5281/zenodo.19861912), Ottoman pages only, with the annotators' line segmentation.

| Set | Manuscripts | Pages | Lines | Script | Use |
|---|---:|---:|---:|---|---|
| Training | 11 | 199 | 2 757 | naskh only | fine-tuning |
| Validation | 2 (one work) | 19 | 412 | naskh | early stopping, tuning |
| Internal test (ACDC-Evaluation) | 17 | 30 | 544 | 7 naskh, 10 other (divani, ta'liq, nastaliq, riq'a, mixed) | evaluated once, never used for tuning |

The split is made by work, never by page. Lines without transcription, lines with transcriber annotations, and (training only) 6 lines with characters outside the base model's codec are excluded.

## Evaluation

**Metric**: character error rate (CER), micro-averaged, spaces included, computed on ground truth and predictions **after the same normalisation function** (`htr_ottoman.normalize`: NFD, vowel marks removed, ک/ك and ی/ي/ى encoding variants unified, verse separators unified as ".", invisible characters and spaces cleaned). Recognition only: lines are cut from the ground-truth segmentation. Confidence intervals: 95 %, bootstrap over manuscripts (groups of at least 3 manuscripts).

| Set | Base model | This model |
|---|---:|---:|
| Validation (2 manuscripts, 412 lines) | 27.76 % | **16.32 %** |
| Internal test, all (17 manuscripts, 544 lines) | 37.03 % [33.4 ; 41.8] | **26.33 % [22.9 ; 31.1]** |
| Internal test, naskh (7 manuscripts, 202 lines) | 35.16 % [29.2 ; 41.3] | 23.70 % [18.4 ; 29.6] |
| Internal test, other scripts (10 manuscripts, 342 lines) | 38.41 % [34.2 ; 45.0] | 28.26 % [24.0 ; 35.6] |
| Internal test, without the 4 multilingual manuscripts (13 manuscripts, 438 lines) | 37.02 % [33.5 ; 41.5] | 26.23 % [22.8 ; 30.8] |

On the internal test, the paired difference is −10.7 points [−11.7 ; −9.6] (relative reduction 28.9 %), and all 17 manuscripts improve. The internal test was evaluated once, with a pre-registered protocol, and is closed since then: no other model has been or will be measured on it.

**Another result, descriptive only (not this model)**: the same fine-tuning with a longer early-stopping patience (15 epochs, cap of 150) and seed 42 reaches 15.60 % on the validation set. It is not published, has no internal-test measure, and was never compared to this model under the project's comparison rule; it is the starting point of the next version (v1.0).

## Limitations

- **Naskh only**: the training data are 100 % naskh; 10 of the 17 internal-test manuscripts use other scripts, with higher error rates.
- **No test from another source**: generalisation is measured only on the internal test, which comes from the same dataset as the training data (same transcription conventions, same annotation platform, same curation team). No open dataset of Ottoman manuscripts met the project's criteria for an external test.
- **Small data**: 2 757 training lines, dominated by one work (about 63 % of the lines).
- **CER depends on normalisation**: the figures above are computed after `normalize()`. A CER computed without it (for example by `ketos test`) is not comparable: the base model uses other encodings (ی, ک) than MAKHZAN (ي/ى, ك).
- **Recognition only**: the CER is measured on ground-truth line segmentation; a full pipeline on raw pages will do worse.
- **Unchanged codec**: the model cannot output characters absent from the base model's codec (for example dotless ٮ and ڡ, ZWNJ). On the internal test it reads fewer digits than the base model (6 of 43 against 18), a descriptive observation on few examples.
- **kraken 7.1.1 `kraken ocr`**: its plain-text output came out reversed on this project's ALTO files; predictions were made through the Python API (below) or `ketos test`. Tested with kraken 7.1.1 on macOS (Apple Silicon) only.

## Usage

```python
from kraken.configs import RecognitionInferenceConfig
from kraken.lib.xml import XMLPage
from kraken.tasks import RecognitionTaskModel
from PIL import Image

model = RecognitionTaskModel.load_model("ota_naskh_makhzan_v0.1.0.safetensors")
config = RecognitionInferenceConfig(bidi_reordering=True)
seg = XMLPage("page.xml").to_container()          # ALTO or PAGE file with baselines
with Image.open(seg.imagename) as im:
    for record in model.predict(im=im, segmentation=seg, config=config):
        print(record.id, record.prediction)       # logical order
```

## Licence and citation

The model is distributed under **CC BY-NC-SA 4.0**, inherited from MAKHZAN: attribution, non-commercial use, share alike. When using it, please cite:

- the training data: Parkes Allen, J., Mullan, J., Nigst, L., Barber, M., Shahid Khan, T., Seydi, M., Chen, D., Weng, Y., Vogler, N., Murel, J., Eshera, O., Berg-Kirkpatrick, T., Smith, D., Bowen Savant, S., Thomas Miller, M., Verkinderen, P. *OpenITI MAKHZAN*, version 2026.1.2, Zenodo, 2026, DOI 10.5281/zenodo.19861912;
- the base model: Kiessling, B. *Printed Ottoman Base Model Trained on the OpenITI Corpus*, Zenodo, 2022, DOI 10.5281/zenodo.7050342;
- this model: Buyukaydin, Y. *Ottoman Turkish handwritten naskh, fine-tuned on MAKHZAN (v0.1.0)*, Zenodo, 2026, DOI [10.5281/zenodo.23502722](https://doi.org/10.5281/zenodo.23502722).

Training and evaluation code (MIT), protocol, decisions and experiment log: the project repository (`htr-ottoman`).
