# Feuille de route

Liste des tickets du projet. Pour lancer un ticket : « fais Fx ».
Statuts : à faire, en cours, fait. Dernière mise à jour : 2026-09-28.

## Vue d'ensemble

| ID | Titre | Dépend de | Statut |
|----|-------|-----------|--------|
| F0 | Mise en place du projet | | fait |
| F1 | `normalize.py` et ses tests | | fait |
| F2 | Téléchargement et extraction de MAKHZAN | | fait |
| F3 | Splits | F2 | fait |
| F4 | Préparation des données pour kraken | F1, F2, F3 | à faire |
| F5 | Évaluation (CER) | F1 | à faire |
| F6 | Modèle de départ | F1, F2 | à faire |
| F7 | Baseline | F4, F5, F6 | à faire |
| F8 | Premier fine-tuning | F7 | à faire |
| F9 | Évaluation interne du modèle affiné | F5, F8 | à faire |
| F10 | Akis | F1, F5 | à faire |
| F11 | Évaluation externe sur Akis | F7, F9, F10 | à faire |
| F12 | Expériences complémentaires | F9 | à faire |
| F13 | Analyse d'erreurs | F9 | à faire |
| F14 | Publication | F11 | à faire |

Phases : données (F1 à F4), référence (F5 à F7), affinage (F8, F9), généralisation externe (F10, F11), approfondissement et publication (F12 à F14).

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
- **Dépend de** : rien. Les règles pourront être complétées après F6 (codec du modèle) et F10 (conventions d'Akis), chaque ajout étant consigné dans DECISIONS.md.
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
- **Statut** : à faire.

---

## F5 · Évaluation (CER)

- **Objectif** : un module d'évaluation fiable, qui donne le CER global et ventilé.
- **Dépend de** : F1.
- **Tâches** :
  - `src/htr_ottoman/evaluate.py` : CER calculé sur des textes normalisés par `normalize`.
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
- **Statut** : à faire.

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
- **Statut** : à faire.

---

## F7 · Baseline

- **Objectif** : mesurer le modèle de départ tel quel, sans affinage, comme point de référence.
- **Dépend de** : F4, F5, F6.
- **Tâches** :
  - Reconnaissance des lignes de la validation et du test interne avec le modèle de départ, sur la segmentation de la vérité terrain.
  - CER avec `evaluate`, avec toutes les ventilations de F5.
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
- **Statut** : à faire.

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
  - Estimer la durée à partir d'un essai court (quelques centaines d'itérations) avant de lancer l'entraînement complet.
  - Consigner l'expérience dans EXPERIMENTS.md (CER validation seulement).
- **Critères d'acceptation** :
  - Entraînement terminé, meilleur modèle choisi sur la validation, sauvegardé dans `models/`.
  - Courbes d'apprentissage enregistrées dans `reports/figures/`.
  - Expérience consignée.
- **Points de décision** :
  - Entraîner en local (MPS) ou sur Colab ou Kaggle (GPU CUDA), selon la durée estimée.
  - Validation des hyperparamètres et du mode de gestion du codec avant le lancement.
  - Accord avant tout entraînement long (CLAUDE.md).
- **Concept à expliquer** : fine-tuning contre entraînement depuis zéro, époque, taux d'apprentissage, surapprentissage et arrêt anticipé, rôle de la validation dans le choix du meilleur modèle.
- **Statut** : à faire.

---

## F9 · Évaluation interne du modèle affiné

- **Objectif** : mesurer la généralisation du modèle affiné sur le test interne (ACDC-Evaluation).
- **Dépend de** : F5, F8.
- **Tâches** :
  - Évaluer le modèle retenu en F8 sur le test interne, une seule fois.
  - CER global, par écriture (naskh contre les autres écritures), par relecture.
  - Comparer avec la baseline F7.
  - Consigner le résultat dans EXPERIMENTS.md.
- **Critères d'acceptation** :
  - Tableau baseline contre modèle affiné, par écriture, avec les effectifs.
  - Consigné dans EXPERIMENTS.md.
- **Points de décision** :
  - Si le résultat est décevant, ne pas régler sur le test interne : revenir à la validation (F8) et consigner la décision.
- **Concept à expliquer** : généralisation dans le domaine contre hors domaine, et pourquoi on ne regarde le test qu'une fois.
- **Statut** : à faire.

---

## F10 · Akis

- **Objectif** : préparer le jeu de test externe Akis dans le format du projet.
- **Dépend de** : F1, F5.
- **Tâches** :
  - Téléchargement via git LFS dans `data/raw/akis/`, avec version ou commit exact noté dans le README. Demander avant tout téléchargement de plus de 1 Go.
  - Conversion au format du projet (table des lignes comme en F2).
  - Comparer les conventions de transcription d'Akis et de MAKHZAN : alphabet, diacritiques, hamza, variantes de lettres, ponctuation.
  - Définir des règles de normalisation communes, ajoutées à `normalize` avec leurs tests et consignées dans DECISIONS.md.
  - Citer Tasdemir et al., DAS 2024 (licence Apache 2.0).
- **Critères d'acceptation** :
  - Akis est converti.
  - Le rapport de comparaison des conventions est dans `reports/`.
  - Les règles communes sont testées et consignées.
  - Seule la partie test d'Akis est utilisée.
- **Points de décision** :
  - Règles de normalisation communes : toute règle ajoutée change le CER de toutes les expériences, qu'il faudra donc recalculer.
  - Quelle partie d'Akis sert à l'évaluation.
- **Concept à expliquer** : git LFS, le décalage de domaine (*domain shift*), et pourquoi des conventions de transcription différentes gonflent artificiellement le CER.
- **Statut** : à faire.

---

## F11 · Évaluation externe sur Akis

- **Objectif** : mesurer la généralisation sur un jeu externe, pour le modèle de départ et le modèle affiné.
- **Dépend de** : F7, F9, F10.
- **Tâches** :
  - CER de la baseline et du modèle affiné sur le test Akis, avec les normalisations communes de F10.
  - Ventilation par écriture si Akis fournit l'information.
  - Comparaison avec les résultats publiés par Tasdemir et al., si le protocole est comparable.
  - Consigner le résultat dans EXPERIMENTS.md.
- **Critères d'acceptation** :
  - Deux lignes dans EXPERIMENTS.md, baseline et modèle affiné.
  - Comparaison avec l'article, en précisant les différences de protocole.
- **Points de décision** : aucun réglage ne doit dépendre de ces résultats (évaluation finale uniquement).
- **Concept à expliquer** : validité externe, et comment comparer honnêtement avec des résultats publiés.
- **Statut** : à faire.

---

## F12 · Expériences complémentaires

- **Objectif** : à préciser selon les résultats. Pistes :
  - entraînement avec ou sans les pages en couche gen2 (décision 4) ;
  - part de *Revnaḳ-ı Būstān* limitée (environ 63 % de l'entraînement) ;
  - ajout d'ACDC-Training. Attention : il ne contient aucune page ottomane (arabe et persan seulement), il s'agirait donc d'un entraînement multilingue.
- **Dépend de** : F9.
- **Tâches, critères, points de décision** : à préciser selon les résultats. Chaque expérience ne change qu'un facteur à la fois et est consignée dans EXPERIMENTS.md.
- **Concept à expliquer** : l'étude d'ablation (ne changer qu'un facteur à la fois).
- **Statut** : à faire.

---

## F13 · Analyse d'erreurs

- **Objectif** : à préciser selon les résultats. Pistes : un notebook d'analyse, les confusions de caractères les plus fréquentes, des exemples d'images de lignes avec vérité terrain et prédiction.
- **Dépend de** : F9.
- **Tâches, critères, points de décision** : à préciser selon les résultats. Les calculs sont dans `htr_ottoman.analysis` ; le notebook ne fait qu'afficher.
- **Concept à expliquer** : l'alignement de deux chaînes et la matrice de confusion au niveau des caractères.
- **Statut** : à faire.

---

## F14 · Publication

- **Objectif** : à préciser selon les résultats. Pistes :
  - README final ;
  - carte du modèle (*model card*) ;
  - dépôt du modèle sous CC BY-NC-SA (hérité de MAKHZAN) ;
  - référencement sur HTR-United.
- **Dépend de** : F11.
- **Tâches, critères, points de décision** : à préciser selon les résultats. Il faudra au moins choisir le lieu du dépôt (Zenodo, par exemple) et la licence du code.
- **Concept à expliquer** : ce que contient une carte de modèle, et comment les licences des données se transmettent au modèle.
- **Statut** : à faire.
