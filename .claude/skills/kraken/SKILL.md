---
name: kraken
description: Référence kraken 7.1 (ketos) pour ce projet HTR ottoman. À lire avant toute commande ketos ou kraken, et avant d'écrire du code qui compile des données, entraîne, affine (fine-tuning), évalue ou fait de l'inférence avec kraken : compilation Arrow, découpe des lignes (baselines, bbox, anciens polygones), normalisation et sens du texte, --load / --resume / --resize, fichiers d'expérience YAML, ketos test.
---

# kraken 7.1 : référence pour le projet

Version installée : **kraken 7.1.1** (`uv run ketos --version`). Toujours lancer via `uv run ketos ...` ou `uv run kraken ...`.
En cas de doute sur une option, **l'aide installée fait foi** (`uv run ketos <commande> --help`) : la doc en ligne diffère parfois (voir section 9).

## Sources

Consultées le 2026-09-28 :

- Doc 7.1, entraînement de la reconnaissance : https://kraken.re/7.1/user_guide/training_recognition.html
- Doc 7.1, inférence : https://kraken.re/7.1/user_guide/inference.html
- Doc 7.1, modèles : https://kraken.re/7.1/user_guide/models.html
- Doc 7.1, migration depuis 6.0 : https://kraken.re/7.1/user_guide/migration_6_0.html
- Doc 7.1, changelog (section « Polygon extractor ») : https://kraken.re/7.1/changelog.html
- Aide installée : `ketos --help`, `ketos compile --help`, `ketos train --help`, `ketos test --help`, `ketos convert --help`
- Code installé (quand la doc ne tranche pas) : `kraken/lib/arrow_dataset.py`, `kraken/lib/dataset/recognition.py`, `kraken/train/vgsl.py`, `kraken/models/loaders.py`

## 1. Formats de modèle

- `.mlmodel` : ancien format CoreML, toujours lu par kraken 7 (chargeur `coreml`, `kraken/models/loaders.py`). C'est le format du modèle de départ OpenITI.
- `.safetensors` : format par défaut depuis 7.0 (migration_6_0).
- `.ckpt` : checkpoints Lightning produits pendant l'entraînement (poids + optimiseur + scheduler + configuration). À la fin, le meilleur checkpoint est converti automatiquement en poids (`--weights-format`, défaut `safetensors`). Conversion manuelle : `ketos convert -o model.safetensors model.ckpt` ; vers CoreML : `--weights-format coreml` (VGSL seulement).
- Modèle Python : `from kraken.models import load_models; load_models(path, tasks=["recognition"])` ; codec : `model.codec.c2l` (0 = blank CTC).

## 2. Préparation des données

Formats d'entrée (`-f`) : `xml` (défaut, ALTO ou PageXML détecté), `alto`, `page`, `path` (image + `.gt.txt`), `binary` (jeu compilé).

**Manifestes** : fichier texte, un chemin par ligne, passé avec `-t` (entraînement) et `-e` (évaluation). Pour un jeu compilé, le manifeste contient le chemin du `.arrow` et on met `-f binary` (training_recognition, « Data Preparation »).

**Compilation** (recommandée, accélère l'entraînement) :

```bash
uv run ketos compile -f alto -o train.arrow page1.xml page2.xml ...
uv run ketos compile -f alto -F liste_des_xml.txt -o train.arrow
```

Options de `ketos compile` (aide installée) :
- `-o` fichier de sortie (défaut `dataset.arrow`) ; `-F` fichier(s) listant les XML.
- `--linetype baselines|bbox` : `baselines` (défaut) extrait des lignes **redressées le long de la ligne de base et masquées par le polygone** ; `bbox` fait un simple rectangle. Le type est enregistré dans les métadonnées du jeu.
- `--force-type` : réécrit seulement le type enregistré, sans changer l'extraction (cas `path`).
- `--skip-empty-lines` (défaut) / `--keep-empty-lines`.
- `--legacy-polygons` : utilise l'**ancien** extracteur de polygones (voir section 3).

**Le texte est stocké brut** : `ketos compile` écrit `line.text` tel quel, sans normalisation (`arrow_dataset.py`, `_extract_line`). La normalisation se fait au chargement (section 4).

## 3. Découpe des lignes : ancien ou nouvel extracteur

- kraken 5 a introduit un nouvel extracteur de polygones, 30 fois plus rapide, mais pas identique à l'ancien : un modèle entraîné avec l'ancien perd un peu (en général moins de 0,25 point) si on lui donne des lignes découpées avec le nouveau (changelog, « Polygon extractor »).
- Chaque modèle porte un drapeau `use_legacy_polygons`. **Le modèle de départ OpenITI a `use_legacy_polygons = True`.**
- Inférence et `ketos test` sur XML : l'extracteur est choisi d'après le drapeau du modèle ; `--no-legacy-polygons` force le nouveau (inference, training_recognition « test »).
- `ketos compile` : **nouvel extracteur par défaut** ; `--legacy-polygons` pour l'ancien. Le statut est enregistré dans le jeu compilé.
- `ketos train` sur jeu compilé : le modèle entraîné hérite du statut du jeu d'entraînement, même avec `--load` d'un modèle « ancien » (avertissement « model will be flagged to use new ») (`train/vgsl.py`, `setup`). Train et validation doivent avoir le même statut (sinon avertissement, le train l'emporte).
- `ketos test` sur jeu compilé : les images de lignes sont **déjà découpées** dans le `.arrow` ; l'extracteur est donc celui choisi à `ketos compile`, et `--no-legacy-polygons` est sans effet. Le type de ligne enregistré dans le jeu est utilisé (aide `--linetype`).

## 4. Normalisation et sens du texte

Options de `ketos train` et `ketos test` (aide installée), appliquées **au chargement** du texte, dans cet ordre (`lib/dataset/recognition.py`) :

1. `-u, --normalization NFD|NFKD|NFC|NFKC` : normalisation Unicode (aucune par défaut) ;
2. `-n, --normalize-whitespace` : normalise les espaces Unicode et retire ceux de début et de fin ;
3. `--reorder / --no-reorder` (défaut `reorder`) : réordonne le texte en ordre d'affichage (algorithme BiDi) ; `--base-dir L|R|auto` fixe la direction de base. À l'inférence, `kraken ... ocr` réapplique BiDi à la sortie (`--reorder` par défaut) : la prédiction revient en ordre logique.

Le modèle de départ a été entraîné avec `normalization: NFD`, `normalize_whitespace: true` (hyperparamètres du modèle).

**Règle du projet** : la seule normalisation du texte est `htr_ottoman.normalize.normalize` (CLAUDE.md). Elle est appliquée **avant** la compilation. Avec `-u NFD -n`, kraken ne change alors plus rien (NFD et espaces déjà faits) : ces options sont sans effet mais restent cohérentes avec le modèle. Ne jamais utiliser `-u` avec une autre forme que NFD.

## 5. Entraînement et fine-tuning

```bash
uv run ketos -d auto -s 42 train --load models/.../modele.mlmodel \
    -f binary -t train.lst -e val.lst -o checkpoints/ --resize union
```

- `--load` : repart des **poids** d'un modèle, nouvelle session (le scheduler repart de zéro). `--resume` : reprend un **checkpoint** avec tout l'état (optimiseur, scheduler, époque), les données sont relues depuis le checkpoint (training_recognition, « Fine-tuning », « Resuming Training »). Arrêt brutal : `checkpoint_abort.ckpt`.
- `--resize` quand le codec du modèle ne couvre pas les données :
  - `fail` (défaut) : arrêt ;
  - `union` : ajoute les nouveaux caractères au codec ;
  - `new` : reconstruit la couche de sortie pour les seuls caractères des données ;
  - `add`, `both` : présents dans l'aide installée, non décrits dans la doc 7.1.
- `--freeze-backbone N` : gèle tout sauf la dernière couche pendant N échantillons (utile sur petit jeu, limite l'oubli).
- Toujours donner `-e` : sans lui, `-p` (défaut 0,9) coupe **au hasard** le train, différemment à chaque session.
- Arrêt : `--quit early` (défaut) sur la précision caractère de validation, `--lag` (défaut 10 évaluations), `--min-epochs`, `--min-delta` ; `--quit fixed` + `-N`.
- Taux d'apprentissage : `-r` (défaut 1e-3), `--schedule` (défaut `constant` ; aussi `cosine` avec `--cos-max`, `--cos-min-lr`, `reduceonplateau`, `1cycle`...), `--warmup` (nombre de pas d'optimisation pour monter progressivement jusqu'à `-r`).
- Autres : `-B` taille de lot (défaut 1), `--augment`, `--optimizer` (défaut AdamW), `--pad` (défaut 16), `--weights-format`.
- Options globales (avant la sous-commande) : `-d` appareil (défaut `auto`), `--precision` (défaut `32-true`), `--workers`, `--threads`, `-s` seed, `-r/--deterministic`.
- Hyperparamètres du modèle de départ : Adam, lr 1e-3, cosine, lot 16, 23 époques.

**Fichiers d'expérience YAML** : `uv run ketos --config configs/exp.yml train`. Options globales au premier niveau (`precision`, `device`, `num_workers`, `num_threads`, seed...), options de la sous-commande sous `train:`. Les clés sont les **noms Python** des options, pas les drapeaux : `training_data`, `evaluation_data`, `format_type`, `checkpoint_path` (pour `-o`), `rop_patience` (pour `--sched-patience`), `weights_format`, `normalization`, `normalize_whitespace`... (training_recognition, « Experiment Files » ; migration_6_0).

## 6. Évaluation

```bash
uv run ketos test -m modele.safetensors -f binary -e test.lst
```

Rapport : CER, WER, précision par écriture, confusions de caractères (training_recognition, « Evaluation »). Options : `-B`, `--linetype`, `--pad`, `-u`, `-n`, `--reorder`, `--base-dir`, `--no-legacy-polygons`. Le CER de référence du projet est celui de `htr_ottoman.evaluate` (F5) ; `ketos test` sert de contrôle croisé. `ketos test` n'applique aux prédictions que `-u` et `-n` (`train/vgsl.py`, `_pred_transforms`), pas nos règles : sur la validation, modèle de départ, 36,2 % contre 27,8 % pour `evaluate`, écart dû aux ی/ک prédits (convention OpenITI imprimé) et aux suites d'espaces (décision 29). Le rapport donne une « Character Accuracy » = 1 − CER.

## 7. Inférence

```bash
uv run kraken -f xml -I "data/*.xml" -o _ocr.xml ocr -m modele.safetensors   # XML déjà segmentés
uv run kraken -i ligne.png sortie.txt ocr -m modele.mlmodel --no-segmentation  # image d'une seule ligne
```

Options utiles de `ocr` : `--reorder/--no-reorder`, `--base-dir`, `--no-legacy-polygons`, `--linetype`, `-B` (inference).

## 8. Pièges pour ce projet

- Modèle de départ « anciens polygones » contre compilation « nouvel extracteur » par défaut : choisir explicitement (`--legacy-polygons` ou non) et le consigner. La baseline (F7) doit utiliser la même découpe que le modèle évalué.
- `--resize fail` par défaut : le train contient `#`, ZWNJ et `ٮ`, absents du codec (décision 23). Sans choix explicite, l'entraînement s'arrête.
- Ne pas laisser kraken couper la validation (`-p`) : toujours `-e` avec le jeu de `splits/`.
- Le texte compilé est brut : normaliser avec `normalize` **avant** `ketos compile`.
- Consigner toute commande d'entraînement ou d'évaluation dans EXPERIMENTS.md (CLAUDE.md) et demander avant tout entraînement long.
- **`kraken ocr` en ligne de commande (7.1.1) renvoie un texte inversé** sur nos ALTO, avec `--reorder` comme avec `--no-reorder` (constaté en F4 sur Doc 2937/597930). L'API Python applique correctement le réglage. Pour prédire : API (`RecognitionTaskModel.predict` avec `RecognitionInferenceConfig(bidi_reordering=True)`) ou `ketos test`, jamais la sortie texte de `kraken ocr`.
- **Processus parallèles** : la reconnaissance et `build_binary_dataset(num_workers>1)` lancent des processus (méthode *spawn* sur macOS) qui relisent le script principal. Toujours exécuter depuis un module ou un fichier avec `if __name__ == "__main__":`, jamais depuis `python -` ou `python -c` (boucle d'erreurs `FileNotFoundError: .../<stdin>`).

## 10. Constats vérifiés dans le projet (F4, 2026-09-28)

- Défauts réels de `ketos train` et `ketos test` (`configs/vgsl.py`, `configs/base.py`) : `normalization` aucune, `normalize_whitespace` activé, `bidi_reordering` activé, `base_dir` auto. **`--load` ne reprend pas ces réglages du modèle chargé** : les donner explicitement (`htr_ottoman.prepare.KRAKEN_TEXT_OPTIONS`).
- `-n` remplace chaque espace Unicode par une espace simple et retire début et fin (`functional_im_transforms.text_whitespace_normalize`), **sans réduire les suites d'espaces** ; le ZWNJ n'est pas touché. Sur nos 3 719 lignes compilées, NFD et `-n` ne changent aucune ligne (test `test_kraken_text_transforms_are_noop`).
- BiDi (`get_display`) remplace les caractères « miroir » (parenthèses...) ; aucun n'est présent dans nos lignes compilées.
- **Le modèle de départ produit l'ordre d'affichage** : avec `bidi_reordering=True`, la sortie est en ordre logique (31,7 % d'écart sur une page de validation, 80 % sans). Il a donc été entraîné avec `--reorder` ; garder `bidi_reordering: true`.
- L'avertissement « Neural network has been trained on mode L images, training set contains mode 1 data » est un **faux positif** : le mode du jeu part de `1` et n'est mis à jour qu'au chargement des lignes, après l'avertissement. Les lignes sont converties en niveaux de gris (1 canal, 256 niveaux) par `ImageInputTransforms`.
- `ArrowIPCRecognitionDataset.__getitem__` **remplace en silence** une ligne illisible par une ligne au hasard (`failed_samples`) : le vérifier (`htr_ottoman.prepare.verify_with_kraken`).
- `build_binary_dataset(num_workers>1)` écrit les lignes dans l'ordre d'achèvement (`imap_unordered`) : compilation non déterministe. Avec `num_workers=0`, deux compilations sont identiques octet pour octet (70 s pour nos 3 719 lignes, ancien extracteur).
- Durée indicative sur MacBook Air M5, MPS : une époque de train (2 763 lignes, lots de 16, 173 pas) en 1 min 50, plus environ 7 min de chargement, validation et conversion pour la première époque.

## 9. Écarts entre la doc 7.1 et l'aide installée

- `--optimizer` : doc « Adam, SGD, RMSprop, Lamb, AdamW » ; installé « Adam, AdamW, AdamW+Muon, SGD, RMSprop », défaut AdamW.
- `--quit` : doc « early, fixed, aneal » ; installé « early, fixed ».
- `--resize` : `add` et `both` existent dans l'aide installée mais ne sont pas décrits dans la doc.
- `--schedule` : la doc cite aussi `cosine_warm_restarts`, absent de l'aide installée.
