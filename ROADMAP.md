# Feuille de route

Liste des tickets du projet. Pour lancer un ticket : « fais Fx ».
Statuts : à faire, en cours, en attente, fait. Dernière mise à jour : 2026-09-29.

## Vue d'ensemble

| ID | Titre | Dépend de | Statut |
|----|-------|-----------|--------|
| F0 | Mise en place du projet | | fait |
| F1 | `normalize.py` et ses tests | | fait |
| F2 | Téléchargement et extraction de MAKHZAN | | fait |
| F3 | Splits | F2 | fait |
| F4 | Préparation des données pour kraken | F1, F2, F3 | fait |
| F5 | Évaluation (CER) | F1 | fait |
| F6 | Modèle de départ | F1, F2 | fait |
| F7 | Baseline | F4, F5, F6 | fait |
| F8 | Premier fine-tuning | F7 | fait |
| F9 | Évaluation interne du modèle affiné | F5, F8 | fait |
| F10 | Jeu de test externe (aucun retenu, décisions 40 et 41) | F1, F5 | fait |
| F11 | Évaluation externe | F7, F9, F10 | en attente |
| F12 | Expériences complémentaires | F9 | fait |
| F13 | Analyse d'erreurs | F9 | fait |
| F14 | Publication | F9 (F11 s'il est rouvert) | à faire |
| F15 | v1.0 : modèle naskh utilisable | F14 | à faire |

Phases : données (F1 à F4), référence (F5 à F7), affinage (F8, F9), généralisation externe (F10, F11), approfondissement et publication (F12 à F14), v1.0 (F15, pas avant F14).

---

## F0 · Mise en place du projet

- **Objectif** : un projet reproductible, avec les données et les décisions de découpage prêtes.
- **Dépend de** : rien.
- **Tâches** :
  - [x] Environnement uv, Python 3.13, kraken 7.1.1, MPS vérifié, `uv.lock` (2026-09-25)
  - [x] Choix du modèle de départ, DOI 10.5281/zenodo.7050342 (2026-09-25)
  - [x] Téléchargement de MAKHZAN 2026.1.2, MD5 vérifiés, `data/raw/` en lecture seule (2026-09-25)
  - [x] Exploration des métadonnées, des notes de version et de l'article JOHD (2026-09-25)
  - [x] Décisions 1 à 8 : test interne, validation par œuvre sur *Manāfi' al-nās*, NFD (2026-09-25 au 2026-09-28)
  - [x] Package `htr_ottoman`, tests, ARCHITECTURE.md, PROJECT.md (2026-09-28)
- **Critères d'acceptation** : `uv sync` puis `uv run pytest` passent ; les deux modules d'analyse redonnent les sorties committées.
- **Points de décision** : aucun (déjà tranchés).
- **Concept à expliquer** : aucun.
- **Statut** : fait.

---

## F1 · `normalize.py` et ses tests

- **Objectif** : une seule fonction de normalisation du texte, appliquée identiquement à la vérité terrain et aux prédictions (décisions 5 et 8).
- **Dépend de** : rien. Les règles pourront être complétées après F6 (codec du modèle), chaque ajout étant consigné dans DECISIONS.md. Depuis F7, `normalize` ne change plus : les conventions d'un nouveau jeu sont traitées par une conversion propre à ce jeu (F10).
- **Tâches** :
  - Écrire `src/htr_ottoman/normalize.py` : une fonction publique `normalize(text: str) -> str`.
  - Règle de base : forme Unicode NFD.
  - Recenser les caractères réellement présents dans les lignes ottomanes de MAKHZAN (à partir du TSV et d'un échantillon d'ALTO) pour proposer les règles complémentaires.
  - Documenter chaque règle dans le code (docstring : quoi, pourquoi, exemple) et dans DECISIONS.md.
  - Écrire `tests/test_normalize.py` : un test par règle, avec des exemples réels (آ, أ, ئ), plus l'idempotence (`normalize(normalize(x)) == normalize(x)`).
- **Critères d'acceptation** :
  - `uv run pytest` passe.
  - La sortie est toujours en NFD (`unicodedata.is_normalized("NFD", ...)`).
  - La fonction est idempotente.
  - Chaque règle a une entrée dans DECISIONS.md et au moins un test.
- **Points de décision** :
  - Quelles règles en plus de NFD : espaces multiples, espaces en début et en fin, marques de direction (RLM, LRM), caractères de largeur nulle (ZWJ, ZWNJ), tatwīl (ـ), chiffres arabes ou persans.
  - Faut-il uniformiser des variantes que MAKHZAN transcrit de façon inégale (ى / ي, ی / ي, ك / ک) ? C'est à trancher avec la liste des caractères sous les yeux.
- **Concept à expliquer** : les formes de normalisation Unicode (NFC, NFD, caractères combinants), et pourquoi une différence d'encodage invisible à l'œil fausse le CER si la vérité terrain et la prédiction ne sont pas traitées de la même façon.
- **Statut** : fait (2026-09-28). Règles : NFD, marques de direction, voyelles, ک→ك, ی selon la position, ZWNJ répétés, espaces (décisions 9 à 14). Inventaire : `reports/ottoman_characters.csv`. 39 tests, dont un sur les 3 868 lignes réelles.

---

## F2 · Téléchargement et extraction de MAKHZAN

- **Objectif** : remplacer le `curl` manuel par un module traçable, puis produire une table de toutes les lignes ottomanes.
- **Dépend de** : rien.
- **Tâches** :
  - `src/htr_ottoman/data/makhzan.py` :
    - téléchargement depuis l'API Zenodo, avec les MD5 lus dans la réponse de l'API ;
    - fichier présent et MD5 valide : rien n'est retéléchargé ;
    - fichier présent mais MD5 invalide : arrêt avec une erreur, sans jamais supprimer quoi que ce soit dans `data/raw/` ;
    - après un téléchargement : fichier mis en lecture seule.
  - Extraction des 30 zips ottomans `Doc<ID>.zip`, emboîtés dans le zip principal, vers `data/interim/makhzan/<DocID>/`.
  - `src/htr_ottoman/data/alto.py` : lecture d'un ALTO v4 (lignes, ligne de base, polygone, texte).
  - Table des lignes, une ligne par `TextLine`, avec les colonnes :
    - identifiants : `doc_id`, `part_id`, `line_id` ;
    - `work` (`Title of Text`) ;
    - métadonnées : `script`, `category`, `dataset_source`, `language` ;
    - couche : `layer`, `is_model_layer` (couche nommée d'après un modèle, par exemple gen2) ;
    - `text`, brut tel que dans l'ALTO, non normalisé ;
    - `is_empty` ;
    - chemins de l'image et de l'ALTO.
  - Tests : lecture d'un ALTO minimal écrit à la main ; comportement du téléchargement quand le fichier existe déjà.
- **Critères d'acceptation** :
  - Une deuxième exécution ne retélécharge rien et le signale.
  - Les MD5 des trois fichiers correspondent à ceux de Zenodo.
  - La table contient 248 pages et 30 manuscrits.
  - Par page, le nombre de lignes non vides et le nombre total de lignes égalent `Transcribed Lines Count` et `Total Lines Count` du TSV (vérifié automatiquement).
  - `data/raw/` n'est pas modifié.
- **Points de décision** :
  - Format de la table des lignes : CSV (lisible) ou Parquet (typé, plus compact).
  - Extraire seulement l'ottoman, ou tout MAKHZAN (utile pour F12 avec ACDC-Training).
- **Concept à expliquer** :
  - sommes de contrôle (MD5) et idempotence (relancer sans effet de bord) ;
  - structure d'un fichier ALTO (page, bloc, ligne, ligne de base, polygone) ;
  - pourquoi une table « une ligne par ligne de texte » simplifie tout le reste.
- **Statut** : fait (2026-09-28). `uv run python -m htr_ottoman.data.makhzan` : MD5 vérifiés, 30 manuscrits extraits (873 Mo), table Parquet de 3 868 lignes identique au TSV page par page, deuxième exécution sans effet. Décisions 17 et 18.

---

## F3 · Splits

- **Objectif** : figer train, validation et test interne dans des fichiers versionnés (décisions 1, 3, 6, 7).
- **Dépend de** : F2.
- **Tâches** :
  - `src/htr_ottoman/splits.py` :
    - train = Research sans *Manāfi' al-nās* ;
    - validation = *Manāfi' al-nās fī al-ṭibb* (Doc 2937, 2939) ;
    - test interne = ACDC-Evaluation ottoman.
  - Écrire les fichiers dans `splits/`, avec la seed et la version de MAKHZAN en en-tête.
  - Seed fixée et enregistrée, pour tout tirage aléatoire futur (ordre, sous-échantillonnage en F12).
  - Test automatique :
    - aucune œuvre, aucun Doc ID ni aucune cote partagés entre deux splits ;
    - Doc 86 et 89 dans le même split ;
    - toutes les pages ottomanes affectées exactement une fois.
- **Critères d'acceptation** :
  - Relancer le module redonne des fichiers identiques octet pour octet.
  - Le test d'étanchéité passe.
  - Les effectifs correspondent à PROJECT.md :
    - train : 11 manuscrits, 199 pages, 2 771 lignes ;
    - validation : 2 manuscrits, 19 pages, 436 lignes ;
    - test interne : 17 manuscrits, 30 pages, 555 lignes.
- **Points de décision** :
  - Granularité des fichiers : liste de Doc ID, de pages ou de lignes.
  - Les 7 pages multilingues du test interne (ottoman avec arabe, persan ou baleybelen) : les garder dans le test interne ou les rapporter à part.
- **Concept à expliquer** : le rôle de chaque jeu (train, validation, test), la fuite de données (*data leakage*), le découpage par groupe, et à quoi sert une seed.
- **Statut** : fait (2026-09-28). `uv run python -m htr_ottoman.splits` : `splits/train.csv`, `val.csv`, `test_interne.csv` (une ligne par page, seed 42), étanchéité vérifiée (œuvre, Doc ID, cote), fichiers identiques octet pour octet à chaque génération, 16 tests. Décisions 19 et 20.

---

## F4 · Préparation des données pour kraken

- **Objectif** : produire dans `data/processed/` des jeux d'entraînement et d'évaluation prêts pour kraken 7.
- **Dépend de** : F1, F2, F3.
- **Tâches** :
  - Vérifier dans la documentation de la version installée (kraken 7.1.1) le format d'entraînement attendu et la commande de compilation (`ketos compile`, format binaire Arrow).
  - Appliquer `normalize` au texte des lignes.
  - Découper les images de lignes comme le modèle de départ l'attend (F6) : lignes de base, anciens polygones (`use_legacy_polygons`), hauteur 120 px, niveaux de gris.
  - Exclure les lignes vides de l'entraînement (règle de CLAUDE.md).
  - Exclure de l'entraînement et de l'évaluation les lignes avec annotations de transcripteur (`{...}`, `(؟)`), et consigner leur nombre (décision 15).
  - Garder la trace des pages en couche gen2 (décision 4).
  - Compiler un jeu par split, et enregistrer le nombre de lignes et la liste des caractères de chaque jeu.
  - Contrôler visuellement quelques images de lignes extraites (dans un notebook, pour l'exploration seulement).
- **Critères d'acceptation** :
  - Un jeu compilé par split.
  - Les nombres de lignes correspondent à F3, lignes vides exclues.
  - Aucun texte non NFD dans les jeux.
  - kraken lit les jeux sans erreur (essai d'entraînement très court, sur quelques lignes).
- **Points de décision** :
  - Normaliser avant la compilation avec notre fonction, ou utiliser l'option de normalisation de kraken. CLAUDE.md impose une seule fonction : il faut vérifier qu'il n'y a pas de double normalisation.
  - Que faire des caractères absents du codec du modèle de départ (dépend de F6).
- **Concept à expliquer** :
  - comment kraken découpe une image de ligne à partir de la ligne de base et du polygone ;
  - ce qu'est un jeu compilé et pourquoi il accélère l'entraînement ;
  - ce qu'est le codec (l'alphabet du modèle).
- **Statut** : fait (2026-09-28). `uv run python -m htr_ottoman.prepare` : 248 ALTO normalisés, `train.arrow` (2 763 lignes), `val.arrow` (412), `test_interne.arrow` (544), anciens polygones, fichiers identiques octet pour octet d'une exécution à l'autre, 3 719 lignes lues par kraken sans erreur, essai d'entraînement d'une époque réussi sur MPS (EXPERIMENTS.md). Réglages de texte de kraken vérifiés sans effet sur notre texte, modèle de départ en ordre d'affichage (BiDi). Skill `.claude/skills/kraken/`. Décisions 25 à 27.

---

## F5 · Évaluation (CER)

- **Objectif** : un module d'évaluation fiable, qui donne le CER global et ventilé.
- **Dépend de** : F1.
- **Tâches** :
  - `src/htr_ottoman/evaluate.py` : CER calculé sur des textes normalisés par `normalize`, prédictions remises en ordre logique (BiDi, décision 26).
  - Ventilations : global, par écriture, par catégorie de relecture, couche gen2 ou non, par manuscrit.
  - CER du test interne avec et sans les 7 pages multilingues (`is_multilingual`, décision 19).
  - Rapporter pour chaque groupe le nombre de lignes et de caractères, pour juger de la taille de l'échantillon.
  - Tests sur des cas calculés à la main : chaînes identiques (CER 0), une substitution, une insertion, une suppression, une chaîne vide, un exemple arabe en NFC contre NFD.
- **Critères d'acceptation** :
  - Tous les cas calculés à la main passent.
  - Le résultat ne dépend pas de la forme Unicode d'entrée.
  - Sur un même jeu, le résultat concorde avec l'outil d'évaluation de kraken (`ketos test`), ou l'écart est expliqué.
- **Points de décision** :
  - Agrégation : erreurs totales / caractères totaux (micro), ou moyenne des CER par ligne (macro).
  - Espaces comptés ou non.
  - Utiliser `ketos test` ou notre propre calcul comme référence.
  - Intervalles de confiance (bootstrap par manuscrit) pour les petits groupes.
- **Concept à expliquer** : la distance d'édition (Levenshtein : substitutions, insertions, suppressions), la définition du CER, et pourquoi un CER sur 30 lignes est beaucoup moins fiable qu'un CER sur 3 000.
- **Statut** : fait (2026-09-28). `evaluate` (CER micro, espaces comptés, bootstrap par manuscrit) et `predict` (API kraken). 21 tests, dont tous les cas calculés à la main et la concordance avec torchmetrics. Contrôle sur la validation avec le modèle de départ : 27,8 % (`evaluate`) contre 36,2 % (`ketos test`), écart expliqué exactement par nos règles de normalisation. Décisions 28 à 30.

---

## F6 · Modèle de départ

- **Objectif** : disposer du modèle OpenITI ottoman imprimé et savoir quels caractères il connaît.
- **Dépend de** : F1, F2.
- **Tâches** :
  - Télécharger le modèle (DOI 10.5281/zenodo.7050342) dans `models/`, via un module traçable, avec vérification MD5.
  - Vérifier que kraken 7.1.1 le charge : le modèle date de 2022, il y a peut-être un format ancien à convertir.
  - Extraire son codec (liste des caractères).
  - Comparer le codec aux caractères des lignes ottomanes de MAKHZAN après `normalize` : caractères communs, caractères présents dans MAKHZAN mais inconnus du modèle, avec leur fréquence.
  - Écrire la comparaison dans `reports/`.
- **Critères d'acceptation** :
  - Le modèle se charge sans erreur.
  - Le rapport liste les caractères inconnus avec leur nombre d'occurrences.
  - Le MD5 est vérifié.
- **Points de décision** :
  - Si des caractères fréquents sont inconnus du modèle : les normaliser (règle ajoutée à F1), ou étendre le codec pendant le fine-tuning (F8).
  - Si kraken 7 ne charge pas le modèle directement : méthode de conversion.
- **Concept à expliquer** : ce qu'est le codec d'un modèle HTR (la couche de sortie, un caractère par classe), et pourquoi un caractère absent du codec ne peut jamais être prédit.
- **Statut** : fait (2026-09-28). `uv run python -m htr_ottoman.base_model` : MD5 vérifié, chargé par kraken 7.1.1 sans conversion (lignes de 120 px, niveaux de gris, lignes de base, anciens polygones). Codec de 196 caractères. `analysis.codec_coverage` : après les règles 8 et 9, 100 % des caractères de la validation connus, 99,92 % du test interne, 99,99 % du train (`reports/codec_coverage.csv`). Décisions 21 à 24.

---

## F7 · Baseline

- **Objectif** : mesurer le modèle de départ tel quel, sans affinage, comme point de référence.
- **Dépend de** : F4, F5, F6.
- **Tâches** :
  - Reconnaissance des lignes de la validation et du test interne avec le modèle de départ, sur la segmentation de la vérité terrain (`data/processed/makhzan/`, anciens polygones). Prédire avec l'API Python (`bidi_reordering=True`) ou `ketos test`, jamais la sortie texte de `kraken ocr`, inversée en 7.1.1 (skill kraken, section 8).
  - CER avec `evaluate`, avec toutes les ventilations de F5. La validation a déjà été mesurée en contrôle de F5 (27,8 %) : F7 refait la mesure avec les prédictions à leur emplacement officiel et ajoute le test interne. Prédictions : `uv run python -m htr_ottoman.predict`.
  - Consigner le résultat dans EXPERIMENTS.md (date, commit, données, modèle, paramètres, CER validation, CER test interne).
  - Sauvegarder les prédictions dans `reports/` pour F13.
- **Critères d'acceptation** :
  - Une ligne dans EXPERIMENTS.md.
  - Les prédictions sont sauvegardées.
  - Les résultats sont reproductibles en relançant le module.
- **Points de décision** :
  - Confirmer l'évaluation sur la segmentation de la vérité terrain (on mesure la reconnaissance seule, pas la segmentation).
  - Consulter une seule fois le test interne ici, puis seulement après le fine-tuning final (F9).
- **Concept à expliquer** : pourquoi une référence est indispensable avant d'entraîner, et la différence entre erreurs de segmentation et erreurs de reconnaissance.
- **Statut** : fait (2026-09-28). Segmentation de la vérité terrain (décision 31), test interne consulté ici puis seulement en F9 (décision 32). CER validation 27,8 %, test interne 37,0 % [33,5 ; 41,8]. Prédictions et tableaux dans `reports/baseline/<jeu>/`, contrôlés par `tests/test_evaluate.py`.

---

## F8 · Premier fine-tuning

- **Objectif** : un premier modèle affiné sur le train, réglé sur la validation.
- **Dépend de** : F7.
- **Tâches** :
  - Premier fichier `configs/` (YAML) :
    - modèle de départ ;
    - jeux de données ;
    - taux d'apprentissage, nombre d'époques et arrêt anticipé sur la validation ;
    - gestion du codec ;
    - seed.
  - `src/htr_ottoman/train.py` : lance kraken à partir de la config, sur MPS.
  - Estimer la durée à partir d'un essai court (quelques centaines d'itérations) avant de lancer l'entraînement complet. Mesure de F4 : 1 min 50 par époque d'entraînement sur MPS (lots de 16), plus la validation à chaque époque.
  - Réglages de texte : `htr_ottoman.prepare.KRAKEN_TEXT_OPTIONS` (décision 26), à donner explicitement.
  - Consigner l'expérience dans EXPERIMENTS.md (CER validation seulement).
- **Critères d'acceptation** :
  - Entraînement terminé, meilleur modèle choisi sur la validation, sauvegardé dans `models/`.
  - Courbes d'apprentissage enregistrées dans `reports/figures/`.
  - Expérience consignée.
- **Points de décision** :
  - Entraîner en local (MPS) ou sur Colab ou Kaggle (GPU CUDA), selon la durée estimée.
  - Validation des hyperparamètres et du mode de gestion du codec avant le lancement : 7 caractères du train sont absents du codec (4 `#`, 2 ZWNJ, 1 ٮ, décision 23). Étendre le codec, ou écarter ces 6 lignes.
  - Accord avant tout entraînement long (CLAUDE.md).
- **Concept à expliquer** : fine-tuning contre entraînement depuis zéro, époque, taux d'apprentissage, surapprentissage et arrêt anticipé, rôle de la validation dans le choix du meilleur modèle.
- **Statut** : fait (2026-09-28). Codec du modèle de départ, 6 lignes hors codec écartées (décision 33) ; Adam, lr 1e-4 constant, MPS (décision 34). 91 époques en 4 h 38, meilleure : 86 (`models/f8_finetune/best_0.8365.safetensors`, décision 35). CER validation 16,3 % (`evaluate`) contre 27,8 % pour la baseline ; écart avec kraken 0,03 point. Découpe imposée par `predict` (décision 36). Courbes : `reports/figures/f8_finetune_courbes.png`.

---

## F9 · Évaluation interne du modèle affiné

- **Objectif** : mesurer la généralisation du modèle affiné sur le test interne (ACDC-Evaluation).
- **Dépend de** : F5, F8.
- **Tâches** :
  - Évaluer le modèle retenu en F8 sur le test interne, une seule fois.
  - CER global, par écriture (naskh contre les autres écritures), par relecture.
  - Comparer avec la baseline F7 (`reports/baseline/test_interne/`, décision 32).
  - Consigner le résultat dans EXPERIMENTS.md.
- **Critères d'acceptation** :
  - Tableau baseline contre modèle affiné, par écriture, avec les effectifs.
  - Consigné dans EXPERIMENTS.md.
- **Points de décision** :
  - Si le résultat est décevant, ne pas régler sur le test interne : revenir à la validation (F8) et consigner la décision.
- **Concept à expliquer** : généralisation dans le domaine contre hors domaine, et pourquoi on ne regarde le test qu'une fois.
- **Statut** : fait (2026-09-28). Pré-enregistrement : décisions 37 et 38. `uv run python -m htr_ottoman.final_eval configs/f9_test_interne.yml` : contrôles bloquants tous passés, dont la prédiction de la baseline refaite, identique octet pour octet à F7. CER test interne **26,3 %** [22,9 ; 31,1] contre 37,0 % pour la baseline ; différence −10,7 points [−11,7 ; −9,6], **gain** (critère principal). Naskh −11,5 points [−12,7 ; −10,5], autres écritures −10,2 [−11,6 ; −8,4] : gain dans les deux groupes. 17 manuscrits améliorés sur 17. `ketos test` : 26,31 % contre 26,33 %. Test interne clos (décision 39). Résultats : `reports/f8_finetune/test_interne/`, `reports/comparaisons/f8_finetune_baseline/test_interne/`, EXPERIMENTS.md.

---

## F10 · Jeu de test externe

- **Objectif** : trouver et préparer un jeu de test externe de manuscrits ottomans, pour mesurer la généralisation en F11.
- **Dépend de** : F1, F5.
- **Fait (2026-09-28)** : Akis téléchargé (dépôt `verimsu/Akis-Ottoman-Dataset`, commit `c7a6e5b`, SHA-256 vérifié contre le pointeur git LFS) et inventorié (`data.akis`, `analysis.akis_inventory`, `reports/akis_sources.csv`, `reports/akis_characters.csv`) : transcriptions en alphabet latin, 13 livres imprimés. **Écarté** (décision 40), gardé comme trace. Piste secondaire non planifiée : échantillon retranscrit en écriture arabe pour mesurer l'oubli de l'imprimé.
- **Tâches** :
  - Rechercher des candidats (HTR-United, Zenodo, RikaOCR, ottoman-rag, eScriptorium...). Critères : ottoman manuscrit ; vérité terrain en écriture arabe faite par des humains ; licence ouverte ; provenance distincte de MAKHZAN ; absent des données du modèle de départ ; au moins quelques centaines de lignes ; idéalement des pages avec lignes de base (ALTO ou PAGE), pour garder la même découpe (décisions 25 et 31). Pour chaque candidat : contenu, taille, écriture, licence, format, conventions, risque de recouvrement avec MAKHZAN.
  - RASAM et TariMa (arabe, pas ottoman) sont exclus : ils sont réservés à l'entraînement de F15.
  - Une fois le jeu choisi : téléchargement (empreinte vérifiée, `data/raw/<jeu>/` en lecture seule, version notée dans le README), table des lignes comme en F2, inventaire, comparaison des conventions avec MAKHZAN, rapport dans `reports/`.
- **Critères d'acceptation** :
  - Le jeu est choisi et consigné dans DECISIONS.md, puis converti.
  - Le rapport de comparaison des conventions est dans `reports/`.
  - `normalize` est inchangée (sinon les résultats de F7 à F9 deviennent incomparables) : les écarts de conventions sont traités par une étape de conversion propre au jeu, testée et consignée.
  - Le jeu n'a jamais servi à l'entraînement et n'y servira jamais (F15 compris).
- **Points de décision** :
  - Choix du jeu parmi les candidats.
  - Conversion des conventions, sans changer `normalize`.
  - Découpe : lignes de base et polygones (même extracteur que MAKHZAN) ou lignes déjà découpées.
  - Lignes à exclure (vides, annotations, texte non ottoman) : règle et effectifs avant application.
- **Concept à expliquer** : git LFS (fait), le décalage de domaine (*domain shift*), et pourquoi des conventions de transcription différentes gonflent artificiellement le CER.
- **Statut** : fait (2026-09-28). Akis écarté (décision 40). Recherche des candidats : aucun jeu ne remplit les critères (décision 41) ; critères, candidats, raisons des exclusions et sources dans [DATASETS.md](DATASETS.md). Les deux plus proches (Osmanlica.com rik'a, CHURRO Osman Ağa) sont interrogés. Si une réponse permet un test propre, la préparation du jeu (tâches ci-dessus) se fera à la réouverture de F11.

---

## F11 · Évaluation externe

- **Objectif** : mesurer la généralisation sur le jeu externe choisi en F10, pour le modèle de départ et le modèle affiné.
- **Dépend de** : F7, F9, F10.
- **Tâches** :
  - Pré-enregistrer l'analyse et la committer avant toute prédiction, comme en F9 (décisions 37, 38 et 41).
  - CER de la baseline et du modèle affiné sur le jeu externe, avec `normalize` et la conversion propre au jeu définie en F10.
  - Ventilation par écriture si le jeu fournit l'information.
  - Comparaison avec des résultats publiés sur ce jeu, s'il en existe et si le protocole est comparable.
  - Consigner le résultat dans EXPERIMENTS.md.
- **Critères d'acceptation** :
  - Deux lignes dans EXPERIMENTS.md, baseline et modèle affiné.
  - Comparaison avec les résultats publiés, s'il y en a, en précisant les différences de protocole.
- **Points de décision** : aucun réglage ne doit dépendre de ces résultats (évaluation finale uniquement).
- **Concept à expliquer** : validité externe, et comment comparer honnêtement avec des résultats publiés.
- **Statut** : en attente (décision 41). Aucun jeu externe ne remplit les critères ; le test interne (F9) est le résultat principal de généralisation. Mails envoyés le 2026-09-28, réponses attendues d'Osmanlica.com (jeu rik'a : licence, droit de publier des scores, origine de la vérité terrain, provenance des documents) et des auteurs de CHURRO (licence du sous-ensemble ottoman, contradictoire selon les sources ; transcription alignée par ligne ; fidélité à la page de l'édition de Kreutel, 1980). À rouvrir avec un pré-enregistrement si une réponse permet un test propre.

---

## F12 · Expériences complémentaires

- **Objectif** : tester sur la validation trois variantes de F8, une seule variable changée à chaque fois, avec une règle de comparaison fixée d'avance (décision 42).
- **Dépend de** : F9.
- **Pistes notées avant l'étape 1** (tri dans la décision 42) :
  - entraînement avec ou sans les pages en couche gen2 (décision 4) : retenue (C) ;
  - part de *Revnaḳ-ı Būstān* limitée (environ 63 % de l'entraînement) : écartée ;
  - ajout d'ACDC-Training (arabe et persan seulement, entraînement multilingue) : renvoyé à F15 ;
  - taux d'apprentissage et programme (F8 : la validation progressait encore après 86 époques à 1e-4 constant) : taux 3e-4 retenu (A), `cosine` écarté (D) ;
  - ancien ou nouvel extracteur de polygones (écart de 0,05 point sur F8, décision 36) : écarté.
- **Tâches** :
  - [x] Étape 1 : analyse des erreurs de F8 et de la baseline sur la **validation seulement** (prédictions déjà sauvegardées) : `analysis.error_analysis`, `reports/erreurs/f8_finetune_baseline/val/` (2026-09-29).
  - [x] Bootstrap apparié par page et règle de la décision 42 : `compare_variant`, avec ses tests (2026-09-29).
  - [x] Décision 42 (variantes, ordre, bruit, règle, limites) ; configs `f8_finetune_seed43.yml` et `f8_finetune_seed44.yml` ; `train` accepte ces seeds pour une copie exacte de F8 seulement (2026-09-29).
  - [x] Bruit : F8 relancé avec les seeds 43 et 44, puis `predict` et `evaluate` sur la validation ; écart et seuil S (2026-09-29). Seed 43 : 76 époques, meilleure 71, 16,84 % ; seed 44 : 49 époques, meilleure 44, 17,75 % ; avec F8 (16,32 %) : écart 1,43 point, **S = 2,86 points** (`compare_variant` sans variante, `reports/bruit/f8_finetune/`).
  - [x] Diagnostic des courbes des trois seeds (`analysis.seed_curves`, CSV d'entraînement seulement) : à époque égale, écart de 0,2 à 0,4 point ; l'écart final vient surtout du moment de l'arrêt (seed 44 arrêtée à l'époque 49, les autres à 76 et 91). En attente de la décision de l'utilisateur avant toute variante.
  - [x] Décision 43 (complément à la décision 42) : règle d'arrêt de F12 = lag 15 et plafond de 150 époques ; référence « F8 lag 15 » (seeds 42, 43, 44) ; lanceur `ketos_capped` (kraken 7.1.1 ignore le plafond avec l'arrêt anticipé) ; `compare_variant` refuse une règle d'arrêt différente de celle de la référence ; contrôle de déterminisme `analysis.same_curve` (2026-09-29).
  - [x] Essai technique du plafond (2 époques, `configs/essai_technique_plafond.yml`, jamais utilisé dans F12) : arrêt au plafond, `best_*.safetensors` produit, `run.json` « plafond » ; époques 1 et 2 identiques à F8 (2026-09-29).
  - [x] Référence F8 lag 15 : seeds 42, 43, 44 (`configs/f8_lag15_seed<N>.yml`), lancées par l'utilisateur ; contrôle de déterminisme de la seed 42 contre F8 jusqu'à l'époque 91 ; nouveau S (même formule). Seed 42 faite (2026-09-30) : 150 époques, arrêt « lag et plafond », meilleure 135, CER validation 15,60 % ; contrôle de déterminisme passé (identique à F8 sur 91 époques). Seed 43 faite (2026-09-30) : 150 époques, arrêt « plafond », meilleure 149 (coupée en progrès, limite pré-enregistrée, règle inchangée), CER validation 15,58 %. Seed 44 faite (2026-10-01) : 150 époques, arrêt « plafond », meilleure 150 (coupée en progrès), CER validation 15,40 %. Nouveau S (2026-10-01) : écart 0,21 point, 2 × écart 0,41 point, **S = 0,5 point** (plancher), `compare_variant` sans variante, `reports/bruit/f8_lag15_seed42/`.
  - [x] B : augmentation d'images (essai d'une époque d'abord, pour la durée), règle d'arrêt de F12. Config `configs/f12_b_augment.yml` (f8_lag15_seed42 + `augment: true`) ; essai technique `configs/essai_technique_b_augment.yml` (plafond 1, complément du 2026-10-01 à la décision 43). Essai fait (2026-10-01) : chargement 6,7 min, époque 112 s (comme F8), aucune ligne remplacée ; estimation pour 150 époques environ 7 h. Run fait (2026-10-01) : 150 époques, arrêt « plafond », meilleure 147, CER validation 15,36 %, époque 1 identique à l'essai. Comparaison `compare_variant` contre f8_lag15_seed42 (2026-10-01) : différence −0,25 point, IC [−0,54 ; +0,12], verdict « pas de différence établie ».
  - [x] A : taux d'apprentissage 3e-4, règle d'arrêt de F12. Config `configs/f12_a_lr3e-4.yml` (f8_lag15_seed42 + `lrate: 0.0003`, vérifié par `tests/test_train.py`) ; essai technique `configs/essai_technique_a_lr3e-4.yml` (plafond 1). Essai fait (2026-10-01) : chargement 7,0 min, époque 115 s (comme F8), aucune ligne remplacée ; estimation pour 150 époques environ 7 h. Run fait (2026-10-01) : 87 époques, arrêt « lag », meilleure 72, CER validation 15,14 %, époque 1 identique à l'essai. Comparaison `compare_variant` contre f8_lag15_seed42 (2026-10-02) : différence −0,46 point (8 erreurs d'écart au seuil S), IC [−0,78 ; −0,12], baisse dans les deux manuscrits, verdict « pas de différence établie ».
  - [x] C : sans les pages gen2 (jeu d'entraînement compilé à part, validation inchangée), règle d'arrêt de F12. Jeu compilé (2026-10-02) par `htr_ottoman.prepare_sans_gen2` : `data/processed/makhzan/train_sans_gen2.arrow`, 18 pages et 254 lignes retirées (Doc 83 et 6398), 2 503 lignes, 181 pages, 9 manuscrits ; `train.arrow` et `val.arrow` inchangés (SHA-256) ; texte dans le codec (`--resize fail`) ; U+0655 (31 fois) et گ U+06AF (15 fois) n'apparaissent plus à l'entraînement (absents de la validation). Config `configs/f12_c_sans_gen2.yml` (f8_lag15_seed42 + `training-data: train_sans_gen2.lst`, vérifié par `tests/test_train.py`) ; essai technique `configs/essai_technique_c_sans_gen2.yml` (plafond 1). Essai fait (2026-10-02, consigné le 2026-10-19) : 2 503 lignes chargées, 157 pas par époque, époque 100 s (F8 : 112 s), aucune ligne remplacée ; perte 1031,408569 et précision 0,708456 à l'époque 1 ; estimation pour 150 époques environ 6 h 45. Run fait (2026-10-19) : 150 époques, arrêt « plafond », meilleure 145, CER validation 16,17 %, époque 1 identique à l'essai ; deux mises en veille pendant le run (194 s à l'époque 31, environ 2 min à l'époque 49), sans effet sur les calculs. Comparaison `compare_variant` contre f8_lag15_seed42 (2026-10-19) : différence +0,5656 point (3 459 erreurs, seuil de régression 3 444,965), IC [+0,2272 ; +0,9012], hausse dans les deux manuscrits, verdict « régression » (effets des pages gen2 et du volume confondus).
  - [x] Pour chaque variante : `compare_variant` contre « F8 lag 15 seed 42 », ligne dans EXPERIMENTS.md (B, A et C, 2026-10-01 au 2026-10-19).
  - [x] Synthèse de F12 (2026-10-19) : [SYNTHESE_F12.md](SYNTHESE_F12.md) (bruit, règle d'arrêt, contrôles, résultats des trois variantes, limites, pistes pour F15) ; résumé et limites dans PROJECT.md.
- **Critères d'acceptation** : deux répétitions et trois variantes consignées dans EXPERIMENTS.md ; pour chaque variante, la conclusion de la règle de la décision 42, rapportée quel qu'en soit le sens. Mesure sur la validation seulement ; jamais sur le test interne, clos (décision 39) ; sur un jeu externe seulement si F11 est rouvert (décision 41).
- **Points de décision** : tranchés par les décisions 42 et 43 (règle d'arrêt : lag 15, plafond 150, plus aucune modification dans F12). Restent : accord de l'utilisateur avant chaque entraînement long ; toute combinaison de variantes gagnantes serait une nouvelle décision.
- **Concept à expliquer** : l'étude d'ablation (ne changer qu'un facteur à la fois) et le bruit entre deux entraînements (expliqués à l'étape 1).
- **Statut** : fait (2026-10-19). Aucune variante établie meilleure (B et A : pas de différence établie ; C : régression) ; modèle publié fixé par la décision 44. Synthèse : [SYNTHESE_F12.md](SYNTHESE_F12.md). Prochain ticket : F13.

---

## F13 · Analyse d'erreurs

- **Objectif** : analyse descriptive des erreurs, sur les prédictions déjà sauvegardées : aucune nouvelle prédiction sur le test interne, aucun choix de modèle ni de réglage (décisions 37 et 39).
- **Dépend de** : F9.
- **Points notés en F9** (à traiter sur les prédictions déjà sauvegardées, sans nouvelle prédiction sur le test interne, décision 39 ; analyses exploratoires, décision 37) :
  - (a) Mesurer quelle part du gain de F9 vient des conventions de transcription (espaces, séparateurs, choix de lettres) plutôt que de la lecture. Indice : le gain est presque uniforme entre écritures (naskh −11,5 points, autres écritures −10,2 ; de −5,6 à −14,7 selon le manuscrit).
  - (b) Expliquer l'écart de 2 caractères entre `ketos test` (21 209) et `evaluate` (21 211) sur le test interne.
- **Plan** (fixé le 2026-10-19, avant toute analyse) :
  - **Jeux et modèles** :
    - validation : baseline, F8 (lag 5) et F8 lag 15 seed 42, prédictions sauvegardées (`reports/baseline/val/`, `reports/f8_finetune/val/`, `reports/f8_lag15_seed42/val/`) ; pas B, A ni C ;
    - test interne : baseline et F8 (lag 5) seulement, prédictions sauvegardées (`reports/baseline/test_interne/`, `reports/f8_finetune/test_interne/`), en mode exploratoire (complément du 2026-10-19 à la décision 39), descriptif seulement ;
    - train : vérité terrain et images seulement (Q5), aucune prédiction.
  - **Q1, conventions contre lecture** (point (a)) : contribution au CER, en points, de chaque catégorie d'erreur de `analysis.error_analysis`, pour la baseline et F8 (lag 5) : global, naskh contre autres écritures, par manuscrit ; test interne, mis à côté de la validation (F12, étape 1). Catégories de convention : espace, séparateur « . », ي / ى, ئ, chiffre, ponctuation ; catégories de lecture : même squelette (points), autre substitution, autre suppression, autre insertion. Échantillon : 10 erreurs par catégorie (toutes s'il y en a moins), tirées parmi les erreurs des deux modèles réunis sur le test interne, avec le modèle d'origine indiqué pour chaque erreur, pour juger si la catégorie automatique est juste. Précision du plan, fixée le 2026-10-20 avant toute lecture (choix de l'utilisateur) : aucune image du test interne (décision 39 inchangée) ; jugement à partir du texte seulement, modèle et catégorie affichés (pas d'aveugle). **« Juste »** : la paire d'erreur surlignée, vue avec 4 cases de contexte de chaque côté, montre bien le type de différence que la catégorie nomme ; pour les catégories dont la question le demande (espace, séparateur « . », chiffre, ponctuation, ئ, ي / ى), l'écart doit en plus être isolé : « voisines identiques » = la case juste avant et la case juste après la paire surlignée sont identiques des deux côtés ; le contexte de 4 cases reste affiché mais n'entre pas dans la règle. Commentaires types : « décalage » (la même forme est juste à côté, de l'autre côté : effet de l'alignement), « zone brouillée » (case juste avant ou juste après différente), « petite marque » (signe posé sur une lettre, montré sur ◌). **Questions** (oui / non / incertain, un commentaire) : espace : « La case surlignée met-elle un blanc (␣) face à rien ou à autre chose, avec les voisines identiques ? » (un autre blanc différent dans une case voisine est ignoré) ; séparateur « . » : « La case surlignée a-t-elle un point « . » d'un côté, face à rien ou à une autre forme, avec les voisines identiques ? » (« . » face à ه ou ة : oui) ; chiffre : « Un chiffre du tableau est-il dans la case surlignée, d'un côté au moins, avec les voisines identiques ? » (chiffre face à une lettre de forme proche : oui, « forme proche » ; un autre chiffre différent du même nombre dans une case voisine est ignoré) ; ponctuation : « Un signe du tableau de ponctuation est-il dans la case surlignée, d'un côté au moins, avec les voisines identiques ? » ; ئ : « La seule différence est-elle la petite marque de hamza (◌ٔ) sur ي ou ى, avec les voisines identiques ? » (autre marque, par exemple ◌ٓ : non, « autre marque ») ; ي / ى : « Les deux formes sont-elles identiques, sauf les deux points dessous, avec les voisines identiques ? » ; même squelette : « Les deux formes sont-elles identiques, sauf les points (ou le petit trait de گ) ? » (formes finales de tracé différent, par exemple ن et ب en fin de mot : non, « forme finale ») ; autre substitution : « Les deux formes sont-elles nettement différentes, au-delà des points ? » (non avec « points seulement », « petite marque » ou « décalage ») ; autre suppression : « Côté vérité terrain, la case surlignée est-elle une lettre entière, sans rien en face et sans la même forme juste à côté en face ? » (non avec « petite marque » ou « décalage ») ; autre insertion : même question, côté prédiction. **Affichage** (page HTML autonome, sans image) : modèle (baseline ou F8 (lag 5)), catégorie et question ; segment de la vérité terrain et segment prédit en gros caractères, de droite à gauche, paire d'erreur surlignée en fort, autres différences du segment en clair ; dessous, grille alignée case par case (une lettre par case, de droite à gauche ; signe combinant sur ◌, espace ␣, rien ∅) ; contexte de 4 cases de chaque côté, coupé au bord de la ligne. Tableaux de référence en haut : chiffres (arabes orientaux et persans), ponctuation, marques (hamza, madda, voyelles), ي et ى, conventions de la grille. Ni image, ni manuscrit, ni identifiant de ligne. **Tirage** : unité = une erreur (une paire alignée) d'un modèle ; erreurs des deux modèles réunies par catégorie (13 440 au total) ; 10 par catégorie (toutes s'il y en a moins), tirage simple, seed 42 ; 10 catégories × 10 = 100 ; chaque catégorie a au moins 59 erreurs (deux modèles réunis), donc aucune n'est incomplète ; une même place peut sortir pour les deux modèles (gardée). echantillon.csv, commité avec la page avant la lecture : identifiant, modèle, catégorie, line_id, doc_id, position dans l'alignement, taille de la catégorie (deux modèles réunis), poids (taille / nombre tiré, pour un taux d'accord global pondéré). Pas de taux par modèle (effectifs trop petits). **Rapport** : (1) par catégorie, oui / non / incertain sur 10, taux d'accord = oui / 10, commentaires comptés ; taux global brut et pondéré ; (2) lecture descriptive du tableau conventions contre lecture : points de CER par catégorie pour la baseline et F8 (lag 5), test interne (exploratoire) à côté de la validation (F12, étape 1), regroupement fixé avant la lecture (choix de l'utilisateur, différent de la liste des catégories de convention du plan, qui comptait aussi chiffre et espace) : conventions = séparateur « . », ponctuation, ئ, ي / ى ; lecture = chiffre, même squelette, autre substitution, autre suppression, autre insertion ; espace rapporté à part, comme ambigu ; somme de chaque groupe, avec les taux d'accord en avertissement ; ni IC, ni verdict. Ajout du 2026-10-20, avant la lecture de l'utilisateur : les sommes conventions / lecture sont données sous deux regroupements, (1) celui du plan (conventions = espace, séparateur « . », ي / ى, ئ, chiffre, ponctuation ; lecture = même squelette, autre substitution, autre suppression, autre insertion) et (2) celui de cette précision, choisi après avoir vu les comptes par catégorie du test interne (aucune ligne vue) ; la conclusion ne retient que ce qui tient sous les deux. **Limites écrites d'avance** : espaces : sans image, on ne peut pas séparer convention (découpage des mots par le transcripteur) et lecture ; jugement sur le texte seulement, par un lecteur qui ne lit pas l'ottoman ; 10 erreurs par catégorie ; alignement : à coût égal, un seul alignement retenu ; avec un CER élevé, une erreur isolée (voisines identiques) est plus rare par hasard. Ordre de la page : groupé par catégorie, dans l'ordre du plan, mélangé à l'intérieur (seed 42).**Complément du 2026-10-20, précisions prises pendant la lecture de l'utilisateur** (après la lecture, avant toute analyse ; `jugements.csv` n'est pas modifié) : (1) voisine absente (début ou fin de ligne, ligne d'un seul caractère) : ne fait pas échouer la condition « voisines identiques » ; (2) « . » et virgule (،) sont presque toujours entourés de deux espaces ; un « non » y vient souvent d'un espace supprimé avec le signe (commentaire « signe supprimé avec un espace ») ; limite : pour le séparateur « . » et la ponctuation, la condition « voisines identiques » compte comme non un signe oublié avec son espace ; (3) entrées non indépendantes : d'après `echantillon.csv`, 27 entrées viennent de 13 lignes qui en portent plusieurs (q1_002 et q1_036 ; q1_005 et q1_008 ; q1_009 et q1_084 ; q1_014 et q1_081 ; q1_020 et q1_062 ; q1_022 et q1_025 ; q1_027 et q1_029 ; q1_033, q1_038 et q1_039 ; q1_034 et q1_059 ; q1_037 et q1_082 ; q1_049 et q1_050 ; q1_052 et q1_100 ; q1_058 et q1_090) ; q1_021 et q1_022, q1_024 et q1_028, notés pendant la lecture, viennent de lignes différentes de Doc 3215 à la vérité terrain identique (1 et 2 caractères) ; (4) alignements ambigus gardés en oui par la règle : q1_038, q1_078 ; (5) q1_097 (autre insertion, baseline, Doc 3388) : la vérité terrain de la ligne n'est pas vide (7 caractères ; ni vide ni vide après `normalize`, gardée à juste titre) ; la prédiction de la baseline en a 27 ; l'alignement place 5 caractères de la vérité terrain au début, 2 à la fin et 20 insertions entre les deux ; la fenêtre de 4 cases autour de la paire (position 13) ne contient que des insertions, d'où un segment de vérité terrain vide sur la page ; rien n'est modifié ; (6) la lecture a été faite avec l'aide du chat Claude du projet sur toutes les entrées (règle mécanique appliquée ensemble ; pas à l'aveugle, comme prévu) : limite ; (7) répartition brute : 37 oui, 63 non, 0 incertain (commit 85ecff7), sans interprétation. (8) chiffre, cas limite : un autre chiffre du même nombre en voisine ne fait pas échouer la condition « voisines identiques » ; un espace ou une lettre en voisine compte normalement (précision ajoutée le 2026-10-20 après le commit 7c2a99d, prise elle aussi pendant la lecture). L'analyse lit explicitement `reports/f13/q1_conventions/jugements.csv` (emplacement choisi par l'utilisateur ; le gabarit vide de `lecture/` reste intact) et s'arrête si le fichier n'a pas 100 réponses non vides oui / non / incertain, une par entrée de `echantillon.csv`.
  - **Q2, écart `ketos test` / `evaluate`** (point (b)) : transformations de `ketos test` (NFD, `-n`, BiDi) appliquées à la vérité terrain de `test_interne.arrow`, comparée ligne à ligne à celle d'`evaluate` (21 209 contre 21 211 caractères). Vérité terrain seulement ; pas d'échantillon.
  - **Q3, encre rouge en niveaux de gris** : pour chaque « . » de Doc 2937 (points rouges, 93 occurrences, décision 21), lu, supprimé ou remplacé, par modèle (validation) ; image en couleur et image en gris reçue par le modèle. En descriptif : Doc 3230 (؞, 23 occurrences), test interne, baseline et F8 (lag 5). Échantillon : 30 à 40 lignes de 2937, lecture à l'aveugle. Précision du plan, fixée le 2026-10-19 avant toute lecture : une entrée par « . », 40 « . » tirés (seed 42) parmi les 86 de Doc 2937 dans la validation compilée (32 lignes) ; lecture en deux temps : (1) gris, la ligne prise dans `val.arrow` et passée par les transformations d'entrée de kraken (1 canal, hauteur 120, marge de 16 px ; seule l'inversion des valeurs est annulée pour l'affichage), question « Vois-tu un point de séparation dans la boîte ou à son bord ? », réponses visible / à peine visible / invisible / incertain ; (2) après cette réponse seulement, bouton « afficher la couleur » : même ligne dans l'image de la page, même boîte, question « Y a-t-il un point de séparation en couleur ? », réponses oui / non / incertain ; la réponse en gris est alors verrouillée ; un commentaire. Aucune prédiction, aucune transcription affichée. Critères en haut de la page : un point de séparation est isolé, entre deux mots, hors points des lettres ; point juste hors de la boîte = incertain, commentaire « boîte décalée ». Boîte large estimée d'après l'encre de la ligne (vers sur deux colonnes : le blanc entre les hémistiches est couvert). Réponses gardées dans le navigateur, CSV (identifiant, réponse gris, réponse couleur, commentaire). Note de lecture de l'utilisateur : pendant la lecture, la question couleur a d'abord été comprise comme « le point est-il d'une autre couleur ? », puis lue comme « sur l'image en couleur, vois-tu un point de séparation ? » ; les réponses couleur concernées ont été corrigées en conséquence ; les réponses en gris n'ont pas été modifiées (verrouillées par la page).
  - **Q4, ي de fin de mot dans Doc 2937** : confusions ي / ى par sens et par position (fin de mot, milieu), par modèle, 2937 contre 2939 (validation). Échantillon : 30 à 40 occurrences en fin de mot dans 2937, lecture à l'aveugle (points visibles ou non sur l'image), pour séparer convention de transcription et erreur de lecture. Précision du plan, fixée le 2026-10-19 avant toute lecture : population = fins de mot ي ou ى de Doc 2937 dans la validation (fin de mot comme la règle 5 de `normalize` ; ي suivi d'une hamza, soit ئ, exclu : 2 occurrences), classées d'après la prédiction sauvegardée de F8 (lag 5), alignée comme dans `evaluate` : correct (même lettre), confondu (l'autre lettre), autre issue (supprimée ou autre lettre). Les 35 autres issues sont exclues : population de 280 fins de mot. Tirage stratifié (seed 42, ordre mélangé), 4 cases (taille dans la population → tirés) : ي × confondu 82 → 18 ; ي × correct 112 → 10 ; ى × correct 84 → 10 ; ى × confondu 2 → 2 (pris en entier, descriptif seulement). Poids de tirage = taille de la case / nombre tiré, enregistrés dans `echantillon.csv` avec la case de chaque entrée, commité avec la page avant la lecture ; la page n'affiche ni la case ni le poids. Après la lecture : proportions pondérées (estimation pour les 280 fins de mot de Doc 2937) et proportions brutes sur l'échantillon. Image en couleur seule ; question « Sous la fin du mot encadré, vois-tu deux points (ou un petit trait, deux points liés) ? », réponses oui / non / incertain, un commentaire ; boîte autour du mot estimée d'après l'encre (comme Q3), agrandissement avec une marge de 2 lettres de chaque côté. Critères en haut de la page : oui = deux points ou un trait court sous la partie gauche du mot, y compris dans la courbe qui descend sous la ligne ; non = aucune marque ; points nettement sous une lettre plus à droite = ne comptent pas (doute : incertain, « autre lettre ? ») ; un seul point net = non, « un point » ; tache, trou ou encre traversante = incertain, « tache » ; bord gauche de la boîte au milieu d'un mot, deux mots, ou fin du mot introuvable = incertain, « boîte décalée ».
  - **Q5, « . » sans encre** : nombre de « . » par manuscrit du train ; part de « . » sans encre visible ; « . » ajoutés et oubliés par chaque modèle sur la validation. Échantillon : 30 à 40 « . » du train (Doc 82 et autres manuscrits), lecture à l'aveugle. Précision du plan, fixée le 2026-10-19 avant toute lecture : 40 « . », seed 42, manuscrits d'au plus 5 « . » pris en entier (Doc 82 : 1, Doc 131 : 4), les 35 autres répartis au prorata des « . » (Doc 3262 : 25, Doc 2891 : 5, Doc 3263 : 5). Consignes de lecture : encre rouge ou noire = oui ; endroit introuvable = incertain, avec le commentaire « boîte décalée ». Précision du critère, ajoutée par l'utilisateur après 9 réponses déjà données selon ce critère : « oui » = une marque de séparation (point rouge ou noir, isolé, hors points des lettres) dans la boîte ou collée à son bord ; « non » = seulement des lettres ; « incertain » = hésitation ou boîte décalée, avec commentaire.
  - **Q6, Doc 3179** (test interne, naskh et chikasté mêlés, 56,5 % pour la baseline, 49,5 % pour F8 (lag 5)) : catégories d'erreurs, S / D / I, CER par ligne, longueur des lignes, comparaison aux autres manuscrits, liste des pires lignes. Échantillon : 30 lignes tirées au hasard (les pires lignes figurent seulement dans un tableau), pour nommer les causes (écriture, mise en page, encre, transcription). Précision du plan, fixée le 2026-10-20 avant toute préparation et toute lecture (choix de l'utilisateur ; images autorisées pour Q6 seulement par le complément du 2026-10-20 à la décision 39, 98f8e89) : **page** : pour chaque ligne, (1) l'image telle que le modèle la voit (gris, polygone, ancien extracteur), (2) le même endroit en couleur avec une marge ; aucun texte, aucune prédiction, aucun CER. **Questions**, réponses oui / non / incertain + commentaire libre ; « incertain » si hésitation : A. Image 1 : des lettres sont-elles coupées par le bord ou par une zone noire ? B. Image 1 : voit-on des morceaux d'une autre ligne (au-dessus ou au-dessous) ? C. Image 2 : y a-t-il de l'écriture au-dessus ou au-dessous de la ligne, plus petite ou entre les mots ? D. Image 2 : une partie de l'écriture est-elle pâle, effacée, tachée, ou le verso transparaît-il ? E. Image 2 : y a-t-il de l'encre rouge ou d'une autre couleur que noir ou brun ? F. Image 2 : la ligne est-elle inclinée ou courbe, ou les mots montent-ils en escalier en fin de mot ? **Échantillon** : 30 lignes de Doc 3179 au hasard (seed 42), parmi les lignes gardées après exclusions. **Limite écrite d'avance** : la transcription elle-même n'est pas jugée (lecteur qui ne lit pas l'ottoman). **Analyse prévue** : comptes par question, puis CER de F8 (lag 5) et de la baseline selon oui / non, descriptif, ni IC ni verdict. Précision (2026-10-20, avant toute préparation) : (1) image 1 comme en Q3 : ligne du jeu compilé du test interne (anciens polygones), transformations d'entrée de kraken (gris, hauteur 120, marge 16 px), inversion annulée pour l'affichage ; réglages tirés de la config et des décisions 33 et 36 ; aucun modèle chargé, même pour lire ses paramètres. (2) Les tableaux du plan (catégories d'erreurs, S / D / I, CER par ligne, longueur des lignes, comparaison aux autres manuscrits, pires lignes) sont calculés seulement après la lecture de l'utilisateur. Précision (2026-10-20, avant toute génération) : Doc 3179 n'a que 13 lignes gardées (une page, aucune exclusion) : le tirage de 30 est impossible. Les 13 lignes sont prises en entier, ordre mélangé avec la seed 42, comme la règle "toutes s'il y en a moins" de Q1 et les petits manuscrits pris en entier en Q5. Le reste est inchangé. Limite : une seule page, même main et même support, observations non indépendantes. Le chiffre de 30 avait été fixé sans vérifier la taille de la population. **Complément du 2026-10-20, précisions prises pendant la lecture de l'utilisateur** (après la lecture, avant toute analyse ; `jugements.csv` n'est pas modifié) : C : la ligne visée est entre les flèches bleues ; les lignes voisines complètes ne comptent pas ; seuls comptent les ajouts plus petits, entre deux lignes ou entre deux mots ; les points et signes des lettres ne comptent pas. A : oui si un trait s'arrête net contre le bord ou une zone noire. B : oui si un trait en haut ou en bas n'est rattaché à aucun mot de la ligne. D : zone nettement plus claire, effacée ou tachée sur la ligne visée. E : seulement l'écriture (lettres, points, signes), les traits de cadre ne comptent pas. F : par rapport aux traits horizontaux de la page. Limites : critères précisés pendant la lecture, après la première entrée ; réponses A, B et C de la première entrée changées après ces précisions, avant la fin de la lecture et avant tout résumé (premières réponses données au chat pour cette entrée : A oui, B oui, C incertain, D oui, E non, F non) ; une capture de la première entrée envoyée au chat Claude du projet, qui n'a donné aucun jugement ; répartition brute (666e109) donnée sans interprétation. **Correction du 2026-10-20 à la limite du complément c8080e6** (c8080e6 n'est pas modifié ; vérifié dans la page et dans `jugements.csv` de 666e109) : la première entrée affichée sur la page est q6_01 (ordre de la page = ordre des identifiants) ; ses réponses finales sont A non, B non, C non, D non, E incertain, F non ; par rapport aux premières réponses notées (A oui, B oui, C incertain, D oui, E non, F non), cinq réponses ont changé : A, B et C, mais aussi D (oui → non) et E (non → incertain) ; seule F est inchangée.
  - **Q7, caractères du train absents de la validation** (٠ ڭ ، ٥ ١ ژ, et گ, U+0655 pour le train de F8) : occurrences par jeu ; sur le test interne, combien la baseline et F8 (lag 5) en lisent correctement ; et l'inverse, les caractères du test interne absents du train (ٮ ڡ ں ە, ZWNJ, chiffres), en signalant ceux qui sont hors du codec et que le modèle ne peut donc pas écrire, dont le ZWNJ (décision 23 ; Q2). Effectifs très petits (36 au plus) : indications seulement. Pas d'échantillon.
  - **Échantillons** : tirés avec la seed 42. Pour chacun, une page HTML autonome et un CSV à remplir par l'utilisateur (identifiant, jugement, commentaire), versionné.
  - **Lecture à l'aveugle** (Q3, Q4, Q5) : la page où l'utilisateur juge l'image n'affiche aucune prédiction ; une seconde page, avec les prédictions, n'est produite qu'une fois le CSV entièrement rempli.
  - **Sorties** : `reports/f13/<question>/` (tableaux, pages, CSV de jugement) ; les sorties tirées du test interne portent la mention « exploratoire, décision 39 ». Calculs dans `htr_ottoman.analysis`.
  - **Garde-fous** : le mode exploratoire de `error_analysis` est une option explicite, ne lit que les `lignes.parquet` sauvegardés et n'appelle jamais `predict` ; `tests/test_predict.py::test_internal_test_is_closed` vérifie déjà que `predict` refuse le test interne ; un nouveau test, écrit avec Q1, vérifie que le mode exploratoire ne charge aucun modèle et n'appelle jamais `predict`. Aucun résultat ne modifie `normalize`, la vérité terrain, un modèle ou un groupe ; une règle suggérée par F13 serait une nouvelle décision pour F15, jamais appliquée aux chiffres de F9.
  - **Ordre** : Q2, Q7, Q5, Q3, Q4, Q1, Q6 (vérité terrain d'abord, puis validation, puis test interne en mode exploratoire).
- **Tâches** :
  - [x] Cadrage et plan (2026-10-19) ; complément du 2026-10-19 à la décision 39.
  - [x] Q2, écart `ketos test` / `evaluate` (2026-10-19) : les 2 caractères sont 2 ZWNJ (U+200C) de la vérité terrain, dans 2 lignes de Doc 3215 (ta'liq), retirés par le réordonnancement BiDi de kraken (`--reorder` ; classe BiDi BN, que l'algorithme retire) ; NFD et `-n` les gardent ; aucun écart sur la validation (pas de ZWNJ). `analysis.ketos_char_count`, `reports/f13/q2_ketos_evaluate/`. Écart constaté le 2026-10-20 (lecture du code, rien recalculé) : `analysis.ketos_char_count` a chargé le modèle de départ pour lire son codec, sur le test interne, sans aucune prédiction (vérité terrain seulement) ; chemin d'appel : `split_table("test_interne")` (ketos_char_count.py:71) → `prepare.select_lines()` → `base_model.codec_chars()` → `base_model.load()` → `kraken.models.load_models`. Même écart que la première génération de Q6. Pour information, `period_ink` (Q5, train), `red_ink` et `final_ya` (Q3 et Q4, validation) et `final_ya_errors` (Q4, train) chargent le modèle de la même façon, hors décision 39. Q1 (`error_analysis`, `category_check`, `category_check_results`) et Q7 (`rare_chars`, codec lu dans `reports/codec_coverage.csv`) ne le chargent pas.
  - [x] Q7, caractères du train absents de la validation (2026-10-19) : 8 caractères du train absents de la validation (، U+0655 ٠ ١ ٥ ژ ڭ گ), dont 5 présents dans le test interne (56 occurrences) ; 12 caractères du test interne absents du train (7 chiffres, ٮ ڡ ں ە, ZWNJ ; 59 occurrences), dont ٮ, ڡ et ZWNJ hors codec, que le modèle ne peut pas écrire. Lecture descriptive (baseline → F8 (lag 5)) : ، 1 → 0 sur 36, chiffres 18 → 6 sur 43, ں ە ڭ 0 → 0 sur 19. `analysis.rare_chars`, `reports/f13/q7_caracteres/`.
  - [x] Q5, « . » sans encre (lecture à l'aveugle). Partie avant la lecture faite (2026-10-19) : 329 « . » dans le train compilé, dans 5 manuscrits sur 11 (Doc 3262 : 236 ; 2891 : 44 ; 3263 : 44 ; 131 : 4 ; 82 : 1, ses 4 autres « . » étant dans des lignes annotées, exclues) ; échantillon de 40 « . » (seed 42 ; Doc 82 et 131 en entier, le reste au prorata : 2891 5, 3262 25, 3263 5) ; page `reports/f13/q5_points/lecture_a_l_aveugle.html`, `analysis.period_ink`. Lecture de l'utilisateur faite (2026-10-19, `jugements.csv`, 40 réponses) : 35 oui, 4 non, 1 incertain. « . » oubliés et ajoutés sur la validation faits (2026-10-19, `analysis.period_errors`, `validation_points.csv`) : 123 « . » (Doc 2937 : 86, Doc 2939 : 37) ; lus : baseline 4, F8 (lag 5) 26, F8 lag 15 26 ; oubliés : 119, 97, 97 ; ajoutés : 2, 2, 4. Pas de seconde page pour Q5 (choix de l'utilisateur : l'échantillon est sur le train, sans prédiction sauvegardée, et une page sur Doc 2937 lèverait l'aveugle de Q3). Seconde lecture mécanique d'après les commentaires : 35 oui, 1 non, 4 incertain. Conclusion descriptive : les « . » du train de l'échantillon correspondent presque tous à une marque visible ; l'hypothèse de la décision 21 n'est pas confirmée sur cet échantillon ; Q3 devient la piste principale pour les oublis de « . » sur la validation.
  - [x] Q3, encre rouge en niveaux de gris (lecture à l'aveugle). Partie avant la lecture faite (2026-10-19) : page `reports/f13/q3_encre_rouge/lecture_a_l_aveugle.html`, `analysis.red_ink`. Lecture de l'utilisateur faite (2026-10-19, `jugements.csv`, 40 entrées) : gris visible 35, à peine visible 2, invisible 3 ; couleur oui 37, non 3 ; aucune entrée « gris visible ou à peine visible, couleur non ». Lecture des « . » de 2937 par chaque modèle faite (2026-10-19, `analysis.red_ink_errors`) : lus sur 86, baseline 4, F8 (lag 5) 12, F8 lag 15 11 ; sur les 35 « . » jugés visibles en gris, F8 (lag 5) en lit 5 ; Doc 3230 (test interne, descriptif) : 0 sur 23 pour la baseline et F8 (lag 5). Conclusion (2026-10-19) : l'hypothèse « l'encre rouge devient invisible en niveaux de gris » n'est pas confirmée sur cet échantillon ; les oublis de « . » relèvent de la lecture, pas de l'image (EXPERIMENTS.md).
  - [x] Q4, ي de fin de mot dans Doc 2937 (lecture à l'aveugle). Partie avant la lecture faite (2026-10-19) : page `reports/f13/q4_ya_final/lecture_a_l_aveugle.html`, `analysis.final_ya` ; agrandissement ×3 (×2 testé sur q4_01 : deux points difficiles à distinguer, page de 1 000 px de large). Lecture de l'utilisateur faite (2026-10-19, `jugements.csv`, 40 réponses) : 24 oui, 11 non, 5 incertain. Trois lectures (2 : boîte décalée ; 3 : « autre lettre ? », règle fixée après la lecture 2) et contrôle de sensibilité ; seuls les « oui » stables. Conclusion (2026-10-19, `analysis.final_ya_errors`) : deux points vus sous la fin du mot dans 11 des 18 confusions ي → ى de F8 (lag 5) tirées, aucun point vu dans 1 à 4 ; 3 des 10 ى lus ى avec points visibles ; estimation pondérée 0,60 avec points vus pour les 280 fins de mot (EXPERIMENTS.md).
  - [x] Q1, conventions contre lecture (mode exploratoire du test interne). Étape 1 faite (2026-10-20) : mode exploratoire d'`analysis.error_analysis` (`--exploratoire-test-interne`) : lit les deux seuls `lignes.parquet` de F9 après vérification de leur SHA-256, n'écrit que sous `reports/f13/`, ne charge aucun modèle et n'appelle ni `predict` ni ketos, comptes et catégories seulement (ni IC, ni bootstrap, ni verdict), mention « exploratoire, décision 39 » ; tests dans `tests/test_error_analysis.py`. Lancé le 2026-10-20 : `reports/f13/q1_conventions/test_interne/` (7 CSV, mention « exploratoire, décision 39 » ; totaux 7 855 et 5 585 erreurs, égaux à ceux d'`evaluate`). Page de lecture faite (2026-10-20) : `reports/f13/q1_conventions/lecture/lecture.html`, `analysis.category_check` (100 erreurs, 10 par catégorie, texte seulement). Lecture de l'utilisateur faite (2026-10-20, `reports/f13/q1_conventions/jugements.csv`, commit 85ecff7) : 37 oui, 63 non, 0 incertain ; précisions prises pendant la lecture dans le plan (complément du 2026-10-20). Analyse faite (2026-10-20, `analysis.category_check_results`) : tableaux 1 à 4 (83e811d), annexe stricte (0f17955) et variante ; conclusion descriptive dans EXPERIMENTS.md (taux d'accord brut 0,37, pondéré 0,32 ; environ 79 % du gain sur le test interne vient des catégories de lecture sous les deux regroupements).
  - [x] Q6, Doc 3179 (mode exploratoire du test interne). Partie avant la lecture faite (2026-10-20) : page `reports/f13/q6_doc3179/lecture_a_l_aveugle.html`, `analysis.doc3179` (13 lignes, toutes prises). Image 1 retrouvée par la position dans `test_interne.arrow` (ordre de compilation vérifié texte par texte : une ligne de Doc 3179 a la même vérité terrain qu'une ligne de Doc 3184). Une première génération a chargé le modèle de départ pour lire son codec (via `select_lines`), sans aucune prédiction ; la page a été régénérée avec `select_lines(with_codec=False)` et le chargement de modèle interdit, sorties identiques à l'octet. Lecture de l'utilisateur faite (2026-10-20, `jugements.csv`, 666e109). Tableaux du plan faits (2026-10-20, `analysis.doc3179_results`, 1bc6c36). Conclusion descriptive dans EXPERIMENTS.md : aucune cause établie sur ces 13 lignes.
  - [x] Reporter dans le ticket F15, en une seule fois à la fin de F13, toutes les pistes pour F15 notées pendant F13 (EXPERIMENTS.md, PROJECT.md), sans rien appliquer. Fait le 2026-10-20 : section « Pistes issues de F13 » du ticket F15, renvoi à SYNTHESE_F12.md pour les pistes de F12 ; ligne ajoutée au ticket F14 (codec lu sans charger le modèle).
- **Critères d'acceptation** : pour chaque question, tableaux et CSV de jugement versionnés, ligne dans EXPERIMENTS.md, lecture descriptive sans conclusion au-delà des chiffres et des jugements.
- **Points de décision** : interprétation de chaque question après la lecture de l'utilisateur ; toute règle de normalisation ou de données suggérée est renvoyée à F15 (nouvelle décision).
- **Concept à expliquer** : l'alignement de deux chaînes et la matrice de confusion au niveau des caractères (au début de Q1).
- **Statut** : fait (clos le 2026-10-20). Q2, Q7, Q5, Q3 et Q4 faits le 2026-10-19, Q1 et Q6 le 2026-10-20 ; pistes reportées dans le ticket F15 (398beb2) ; synthèse : [SYNTHESE_F13.md](SYNTHESE_F13.md) (7883afb). Prochain ticket : F14.

---

## F14 · Publication

- **Modèle publié** : fixé par la décision 44 : F8 (lag 5, seed 42), `models/f8_finetune/best_0.8365.safetensors` (époque 86), le seul modèle affiné évalué sur le test interne (F9 : 26,3 %). F8 lag 15 seed 42 n'est pas publié ; il est mentionné dans la carte du modèle et les limites, et sert de point de départ à F15.
- **Objectif** : à préciser selon les résultats. Pistes :
  - README final ;
  - carte du modèle (*model card*) ;
  - dépôt du modèle sous CC BY-NC-SA (hérité de MAKHZAN), avec le drapeau `use_legacy_polygons` corrigé (décision 36) ;
  - référencement sur HTR-United.
  - lire le codec du modèle de départ sans le charger, dans tous les modules : `prepare.select_lines` le charge via `base_model.codec_chars` (écarts de Q2, 11b9416, et de Q6, 5236bc4 ; option `with_codec=False` ajoutée en Q6 ; source possible : `reports/codec_coverage.csv`).
- **Dépend de** : F9 ; F11 s'il est rouvert (décision 41).
- **Tâches, critères, points de décision** : à préciser selon les résultats. Il faudra au moins choisir le lieu du dépôt (Zenodo, par exemple) et la licence du code.
- **Concept à expliquer** : ce que contient une carte de modèle, et comment les licences des données se transmettent au modèle.
- **Statut** : à faire.

---

## F15 · v1.0 : modèle naskh utilisable

- **Objectif** : un modèle naskh utilisable en pratique, avec un CER inférieur à 10 % sur un nouveau jeu de test réservé.
- **Dépend de** : F14. À ne pas commencer avant F14.
- **Tâches** :
  - Constituer d'abord le nouveau jeu de test réservé, avant tout entraînement de F15 : manuscrits naskh, ni la validation (*Manāfi' al-nās*) ni ACDC, aucune œuvre en commun avec les données d'entraînement (décision 6). Le figer dans `splits/` avec la seed, et ne le consulter qu'une fois, pour le modèle final.
  - Ajouter les leviers dans cet ordre, un à la fois, en mesurant l'effet de chacun sur la validation :
    1. données ouvertes : ACDC-Training (arabe et persan, voir F12), RASAM, TariMa ;
    2. transcriptions de l'utilisateur, corrigées dans eScriptorium ;
    3. meilleurs réglages trouvés en F12.
  - Consigner chaque expérience dans EXPERIMENTS.md.
  - Publier le modèle sous CC BY-NC-SA (hérité de MAKHZAN), avec une fiche : données et licences, protocole, CER par écriture, limites, citation.
- **Pistes issues de F13** (reportées le 2026-10-20, à la fin de F13 ; hypothèses non testées, rien n'est appliqué ; toute règle de normalisation ou de données serait une nouvelle décision, jamais appliquée aux chiffres de F9) :
  - *Données* :
    - chiffres : sur le test interne, F8 (lag 5) en lit moins que la baseline (6 sur 43 contre 18) ; chiffres rares dans le train (4) ; hypothèse non établie d'un oubli par l'affinage ; données ou exemples synthétiques contenant des chiffres (proposition ajoutée au report, absente de la conclusion de Q7) (Q7, 5a91fec) ;
    - séparateurs « . » : peu d'exemples dans le train (329, dont 236 dans Doc 3262) ; sur la validation, les « . » visibles sont souvent non écrits ou lus ه ; ressemblance entre un rond rouge et un ه final (Q3, 04f9e98 ; Q5, 013367f) ;
    - virgule ، : souvent lue ه (9 sur 36), lien possible avec les séparateurs (Q7, 5a91fec) ;
    - yāʾ final : train à 82 % de ى en fin de mot (3 037 contre 668 ; 7 manuscrits sur 11), F8 écrit ى pour des yāʾ finaux aux points visibles (Q4, 6736239) ;
    - écriture mêlée naskh et chikasté (entraînement 100 % naskh) ; pages à l'encre dégradée dans l'entraînement (Q6, 6c08707).
  - *Conventions et normalisation* :
    - ي / ى en fin de mot : une règle les fusionnant dans l'évaluation masquerait des erreurs de lecture ; toute règle serait une nouvelle décision (Q4, 6736239) ;
    - ە presque toujours supprimée (10 sur 11) : convention de transcription possible ; règle de normalisation éventuelle, par décision, jamais rétroactive (Q7, 5a91fec).
  - *Alignement et catégories* :
    - un alignement qui traite un signe et son espace collé ensemble ; une catégorie ئ distinguant la hamza seule de la lettre entière (Q1, d1d9526) ;
    - ه / ة : à examiner, Q1 n'apporte rien de plus (Q1, d1d9526 ; piste non définie dans une conclusion antérieure ; origine : remarque faite dans le chat pendant la lecture de Q1 ; le commentaire de q1_064 est vide, 85ecff7).
  - *Relecture avec un lecteur de l'ottoman* :
    - relecture ciblée de la vérité terrain de Doc 2937 (ى aux points visibles) ; place des points du yāʾ final (Q4, 6736239) ;
    - espaces de Doc 3179 (Q6, 6c08707).
- **Pistes issues de F12** : SYNTHESE_F12.md, section 7 (e3424f6) : plafond d'époques, taux 3e-4, augmentation, témoin pour les pages gen2, validation plus large et plusieurs seeds.
- **Critères d'acceptation** :
  - CER inférieur à 10 % (`evaluate`) sur le nouveau jeu de test réservé, mesuré une seule fois.
  - Modèle publié sous CC BY-NC-SA, avec sa fiche.
  - Expériences consignées dans EXPERIMENTS.md.
- **Points de décision** :
  - Composition du nouveau jeu de test (source, manuscrits, taille), à trancher avant tout entraînement.
  - Licences de RASAM, de TariMa et des transcriptions de l'utilisateur : vérifier qu'elles permettent une publication sous CC BY-NC-SA.
  - Conventions de transcription de chaque nouvelle source : règles à ajouter à `normalize` (toute règle ajoutée change le CER de toutes les expériences, voir F10).
  - Si le seuil n'est pas atteint après les trois leviers : ne pas régler sur le test réservé, revenir à la validation et consigner la décision.
- **Concept à expliquer** : pourquoi un jeu de test déjà consulté ne peut plus servir de mesure finale, et ce qu'apportent des données d'autres langues ou d'autres mains (transfert).
- **Statut** : à faire (pas avant F14).
