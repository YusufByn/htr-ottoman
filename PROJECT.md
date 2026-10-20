# Projet HTR ottoman

Résumé du projet et état d'avancement. Mis à jour à chaque étape terminée.
Dernière mise à jour : 2026-10-20.

## 1. Résumé

Reconnaissance automatique d'écriture manuscrite (HTR) sur des manuscrits en turc ottoman, avec kraken.
On part d'un modèle entraîné sur de l'**imprimé** ottoman (OpenITI) et on l'affine sur les manuscrits ottomans de MAKHZAN.

**Question de recherche** : dans quelle mesure ce modèle affiné généralise-t-il à des manuscrits jamais vus ? Le résultat principal est celui du test interne (ACDC-Evaluation, F9). Aucun jeu externe de manuscrits ottomans ne remplit les critères à ce jour (décision 41) : il n'y a pas de test d'une autre provenance (voir les limites, section 7).

Projet de recherche et portfolio.

## 2. Données et modèle de départ

| Ressource | Version | Rôle | Licence |
|-----------|---------|------|---------|
| OpenITI MAKHZAN, partie ottomane | 2026.1.2, DOI 10.5281/zenodo.19861912 | entraînement, validation, test interne | CC BY-NC-SA 4.0 |
| Akis, jeu de test public | dépôt `verimsu/Akis-Ottoman-Dataset`, commit `c7a6e5b` (2024-09-14) | **écarté** comme test (décision 40) : transcriptions en alphabet latin, livres imprimés ; téléchargé et inventorié, gardé comme trace | Apache 2.0, citer Tasdemir et al., DAS 2024 |
| Modèle OpenITI ottoman imprimé | DOI 10.5281/zenodo.7050342 (kraken, CER annoncé 4,22 %). Lignes de 120 px en niveaux de gris, lignes de base, NFD ; codec de 196 caractères | modèle de départ | CC0 |

Tout modèle dérivé de MAKHZAN est sous CC BY-NC-SA. Détails et MD5 : [README](README.md). État des données ouvertes pour l'HTR ottoman manuscrit, critères d'un test externe et raisons des exclusions : [DATASETS.md](DATASETS.md).

## 3. Protocole d'évaluation

| Jeu | Contenu | Manuscrits | Pages | Lignes transcrites | Décisions |
|-----|---------|-----------:|------:|-------------------:|-----------|
| Entraînement | Research, sauf l'œuvre de validation (6 œuvres) | 11 | 199 | 2 771 | 2, 3, 6 |
| Validation | *Manāfi' al-nās fī al-ṭibb* (Doc 2937, 2939) | 2 | 19 | 436 | 7 |
| Test interne | ACDC-Evaluation ottoman, jamais utilisé pour le réglage ; 7 pages multilingues marquées ; clos depuis F9 | 17 | 30 | 555 | 1, 19, 39 |
| Test externe | Aucun jeu ne remplit les critères (DATASETS.md) ; Akis écarté. F11 clos le 2026-10-20 sans jeu externe (aucune réponse d'Osmanlica.com ni des auteurs de CHURRO), il ne sera pas rouvert ; une réponse tardive éventuelle alimenterait F15, avec un pré-enregistrement committé avant toute utilisation | aucun | aucune | aucune | 40, 41 |

- Découpage par œuvre : toutes les copies d'une œuvre sont dans le même jeu (décision 6).
- Les lignes sans transcription sont exclues de l'entraînement.
- Les lignes contenant des annotations de transcripteur (`{...}`, `(؟)`, environ 43) sont exclues de l'entraînement et de l'évaluation (décision 15). Les 6 lignes du train contenant un caractère absent du codec du modèle de départ (#, ZWNJ, ٮ) sont aussi écartées de l'entraînement (décision 33). Lignes compilées pour kraken : train 2 757, validation 412, test interne 544 (`reports/processed_datasets.csv`).
- **Métrique** : CER (taux d'erreur par caractère), calculé sur vérité terrain et prédictions passées par la même fonction `normalize` : NFD, voyelles supprimées, ک et ی unifiés, séparateurs de vers unifiés en ".", ڛ → س, espaces et invisibles nettoyés (décisions 5, 9 à 14, 21, 22). CER micro, espaces comptés (décision 28), rapporté au global, par écriture, naskh contre autres écritures, par catégorie de relecture, par couche gen2 (si le jeu en contient) et par manuscrit, avec un intervalle de confiance à 95 % par bootstrap sur les manuscrits quand le groupe en compte au moins 3 (décision 30). Référence : `evaluate` ; `ketos test` en contrôle (décision 29). Comparaison de deux modèles : différence de CER avec un intervalle par bootstrap apparié sur les manuscrits (décisions 37 et 38).
- Découpage figé dans `splits/train.csv`, `val.csv`, `test_interne.csv` (une ligne par page, seed 42), étanchéité vérifiée par les tests (décision 20).
- CER du test interne rapporté avec et sans les pages multilingues (décision 19).
- **Segmentation** : évaluation sur les lignes tracées par les annotateurs, pour mesurer la reconnaissance seule (décision 31).
- **Test interne consulté deux fois seulement** : baseline (F7) et modèle affiné final (F9) ; tout réglage se fait sur la validation (décision 32). L'évaluation de F9 a été pré-enregistrée (décisions 37 et 38). Le test interne est **clos** depuis F9 : plus aucune prédiction dessus (décision 39).

## 4. Fonctionnalités

| Fonctionnalité | État |
|----------------|------|
| Vérification de l'environnement (kraken, MPS) : `scripts/check_mps.py` | fait |
| Inventaire des manuscrits ottomans : `analysis.inventory_ottoman` | fait |
| Comparaison Research / ACDC-Evaluation, par manuscrit et par œuvre : `analysis.compare_ottoman_sources` | fait |
| Téléchargement de MAKHZAN avec vérification MD5, idempotent : `data.makhzan` | fait |
| Extraction des 30 manuscrits ottomans et table des lignes (Parquet, 3 868 lignes) : `data.makhzan` | fait |
| Inventaire des caractères des lignes ottomanes : `analysis.char_inventory` | fait |
| Normalisation (NFD + 8 règles) et 43 tests : `normalize` | fait |
| Création des splits, contrôle d'étanchéité : `splits` | fait |
| Préparation pour kraken : ALTO normalisés, jeux compilés (anciens polygones), vérification de lecture : `prepare` | fait |
| Modèle de départ : téléchargement, chargement, codec : `base_model` | fait |
| Couverture du codec par MAKHZAN : `analysis.codec_coverage` | fait |
| Prédiction ligne par ligne (API kraken) : `predict` | fait |
| Évaluation (CER micro ventilé, bootstrap par manuscrit) : `evaluate` | fait |
| Baseline du modèle de départ, validation et test interne : `predict` + `evaluate`, `reports/baseline/` | fait |
| Fine-tuning kraken piloté par une config (`configs/`), garde-fous, courbes : `train` | fait |
| Comparaison appariée de deux modèles (bootstrap apparié sur les manuscrits) : `compare` | fait |
| Évaluation pré-enregistrée avec contrôles bloquants (empreintes, découpe, effectifs, baseline refaite à l'octet) : `final_eval` | fait (F9) |
| Analyse des erreurs de deux modèles sur la validation (catégories, confusions, longueur, manuscrit, pires lignes) : `analysis.error_analysis` | fait (F12, étape 1) |
| Comparaison d'une variante à F8 sur la validation (bruit entre seeds, bootstrap apparié par page, règle de la décision 42) : `compare_variant` | fait (F12) ; bruit mesuré (lag 5, puis lag 15 : S = 0,5 point) |
| Diagnostic des courbes de validation des répétitions (époques égales, oscillations, arrêts simulés) : `analysis.seed_curves` | fait (F12) |
| Arrêt anticipé avec plafond d'époques (lag 15, 150 époques), que kraken 7.1.1 ne permet pas seul : `ketos_capped`, choisi par `train` | fait (F12, décision 43) |
| Contrôle de déterminisme (mêmes métriques époque par époque) : `analysis.same_curve` | fait (F12) |
| Jeu d'entraînement sans les pages gen2 (variante C, décision 42), compilé à part : `prepare_sans_gen2` | fait (F12) : 2 503 lignes (254 retirées, 18 pages) |
| Mode exploratoire du test interne (prédictions sauvegardées de F9 seulement, SHA-256 vérifiés, jamais `predict`, sorties sous `reports/f13/`) : `analysis.error_analysis --exploratoire-test-interne` | fait (F13, décision 39 et complément du 2026-10-19) |
| Pages de lecture humaine (échantillon seed 42, page HTML autonome, réponses gardées dans le navigateur, CSV de jugements versionné) et analyses après lecture : `analysis.period_ink` / `period_errors` (Q5), `red_ink` / `red_ink_errors` (Q3), `final_ya` / `final_ya_errors` (Q4), `category_check` / `category_check_results` (Q1), `doc3179` / `doc3179_results` (Q6) ; `ketos_char_count` (Q2), `rare_chars` (Q7) | fait (F13) |
| Téléchargement d'Akis (git LFS, SHA-256 vérifié contre le pointeur), table des lignes et inventaire : `data.akis`, `analysis.akis_inventory` | fait (F10, vérification ; Akis écarté, décision 40) |

## 5. État d'avancement

Voir [ROADMAP.md](ROADMAP.md) : liste des tickets F0 à F15, avec leurs dépendances et leur statut.

## 6. Résultats clés

**Baseline (F7)** : modèle de départ sans affinage, segmentation de la vérité terrain, CER `evaluate`.

| Jeu | Manuscrits | Lignes | CER | IC 95 % |
|-----|-----------:|-------:|----:|---------|
| Validation | 2 | 412 | **27,8 %** | non calculé (2 manuscrits) |
| Test interne | 17 | 544 | **37,0 %** | [33,5 ; 41,8] |
| Test interne sans multilingue | 13 | 438 | 37,0 % | [33,5 ; 41,5] |

Sur le test interne : naskh 35,2 % (7 manuscrits), divani 39,2 % (3), relu deux fois 34,3 %, une fois 41,0 % ; de 23,2 % à 56,5 % selon le manuscrit. Les suppressions (3 631) y pèsent presque autant que les substitutions (3 820). Détail dans `reports/baseline/` et [EXPERIMENTS.md](EXPERIMENTS.md).

**Premier fine-tuning (F8)** : 91 époques (meilleure : 86), Adam, lr 1e-4 constant, codec du modèle de départ. Choisi sur la validation seulement ; mesuré une fois sur le test interne en F9, ci-dessous.

| Modèle | CER validation | Doc 2937 | Doc 2939 |
|--------|---------------:|---------:|---------:|
| Modèle de départ (F7) | 27,8 % | 27,6 % | 27,9 % |
| Essai, 1 époque | 27,3 % | 27,1 % | 27,4 % |
| **F8** | **16,3 %** | 17,2 % | 15,6 % |

Le CER de kraken (16,35 %) et celui de `evaluate` coïncident à 0,03 point près : le modèle affiné a adopté les conventions de MAKHZAN. Courbes : `reports/figures/f8_finetune_courbes.png`.

**Analyse des erreurs sur la validation (F12, étape 1)**, contribution au CER en points (baseline → F8) : espaces 7,1 → 3,7 ; séparateur « . » 0,56 → 0,46 ; ي / ى 0,66 → 0,42 ; ئ 0,07 → 0,07 ; chiffres et ponctuation 0,04 → 0 ; lettres (substitutions, suppressions, insertions) 19,3 → 11,6. Environ 30 % du gain de la validation vient des espaces, les deux tiers des lettres. Les suppressions dominent toujours les insertions (prédictions 4 % plus courtes que la vérité terrain). Détail : `reports/erreurs/f8_finetune_baseline/val/`.

**Bruit entre entraînements (F12, décision 42)** : F8 répété à l'identique avec deux autres seeds. CER de validation : seed 42 (F8) 16,32 %, seed 43 16,84 %, seed 44 17,75 % ; écart 1,43 point, seuil S = 2,86 points. À époque égale, les trois courbes restent à 0,2 à 0,4 point l'une de l'autre : l'écart final vient surtout du moment où l'arrêt anticipé (5 époques sans progrès) s'est déclenché (époque 49 pour la seed 44, 76 et 91 pour les autres). Détail : `reports/bruit/f8_finetune/`, `reports/figures/f12_bruit_seeds.png`.

**Bruit avec la règle d'arrêt de F12 (décision 43 : lag 15, plafond 150)** : CER de validation de « F8 lag 15 » : seed 42 15,60 %, seed 43 15,58 %, seed 44 15,40 % ; écart 0,21 point, 2 × écart 0,41 point, **seuil S = 0,5 point** (plancher). Une variante doit donc faire au moins 107 erreurs de moins que la seed 42 (3 338 sur 21 393 caractères), avec un IC par page sous 0 et une baisse dans les deux manuscrits. Seeds 43 et 44 coupées par le plafond alors qu'elles progressaient. Détail : `reports/bruit/f8_lag15_seed42/`.

**Variantes de F12 (décisions 42 et 43)** : trois variantes de F8 lag 15 seed 42, une seule variable changée chacune, comparées à elle sur la validation par `compare_variant` (S = 0,5 point). Référence : 15,60 % (3 338 erreurs).

| Variante | CER validation | Différence [IC 95 % par page] | Doc 2937 / Doc 2939 | Verdict |
|----------|---------------:|-------------------------------|---------------------|---------|
| B, augmentation d'images | 15,36 % | −0,25 point [−0,54 ; +0,12] | baisse / baisse | pas de différence établie |
| A, taux 3e-4 | 15,14 % | −0,46 point [−0,78 ; −0,12] | baisse / baisse | pas de différence établie (à 8 erreurs du seuil de gain) |
| C, sans les pages gen2 | 16,17 % | +0,57 point [+0,23 ; +0,90] | hausse / hausse | régression |

Aucune variante n'est établie meilleure ; « pas de différence établie » veut dire que la règle ne permet pas de conclure. Pour C, l'effet des pages gen2 et celui de la baisse du volume (254 lignes et 2 manuscrits en moins) sont confondus. D'après la décision 44, le modèle publié en F14 reste F8 (lag 5). Synthèse complète, contrôles, limites et pistes pour F15 : [SYNTHESE_F12.md](SYNTHESE_F12.md).

**Évaluation interne (F9)** : modèle F8 sur le test interne, analyse pré-enregistrée (décisions 37 et 38), seconde et dernière consultation. Différence = CER F8 moins CER baseline, IC 95 % par bootstrap apparié sur les manuscrits. Conclusion selon la règle de la décision 38 : gain si l'IC est entièrement sous 0.

| Groupe | Manuscrits | Lignes | Baseline | F8 | Différence [IC 95 %] | Conclusion |
|--------|-----------:|-------:|---------:|---:|----------------------|------------|
| **Toutes les pages** (critère principal) | 17 | 544 | 37,0 % | **26,3 %** [22,9 ; 31,1] | **−10,7 points** [−11,7 ; −9,6] | **gain** |
| Sans les 7 pages multilingues | 13 | 438 | 37,0 % | 26,2 % [22,8 ; 30,8] | −10,8 [−12,1 ; −9,6] | descriptif |
| Naskh | 7 | 202 | 35,2 % | 23,7 % [18,4 ; 29,6] | −11,5 [−12,7 ; −10,5] | **gain** |
| Autres écritures (mixtes comprises) | 10 | 342 | 38,4 % | 28,3 % [24,0 ; 35,6] | −10,2 [−11,6 ; −8,4] | **gain** |
| Relu une fois | 8 | 196 | 41,0 % | 30,2 % | −10,8 [−12,5 ; −8,6] | descriptif |
| Relu deux fois | 9 | 348 | 34,3 % | 23,7 % | −10,7 [−11,8 ; −9,5] | descriptif |

Réduction relative : 28,9 % ; 17 manuscrits améliorés sur 17 (écart de −5,6 à −14,7 points). Par écriture, sans IC ni conclusion (baseline → F8) : divani 39,2 → 28,2 %, nastaliq 41,2 → 29,6, taliq 35,1 → 24,9, riqa 26,4 → 18,8, naskh_varied 46,1 → 40,5, naskh_shikaste_mixed 56,5 → 49,5. Test d'oubli des écritures non naskh (décision 37) : oubli non établi. Substitutions, suppressions, insertions : 2 793 / 2 418 / 374 contre 3 820 / 3 631 / 404. `ketos test` : 26,31 % contre 26,33 % pour `evaluate`. Détail : `reports/comparaisons/f8_finetune_baseline/test_interne/` et [EXPERIMENTS.md](EXPERIMENTS.md).

**Analyse d'erreurs (F13)**, descriptive, sans IC ni verdict ; test interne en mode exploratoire (décision 39) ; synthèse complète dans [SYNTHESE_F13.md](SYNTHESE_F13.md) :

- **Q2** : l'écart de 2 caractères entre `ketos test` et `evaluate` sur le test interne vient de 2 ZWNJ retirés par le réordonnancement BiDi de kraken ; 5 erreurs d'écart restent non expliquées (0,02 point).
- **Q7** : 8 caractères du train absents de la validation, 12 caractères du test interne absents du train (dont 3 hors codec) ; sur le test interne, F8 (lag 5) lit 6 chiffres sur 43 (baseline 18). Hypothèse non établie : oubli par l'affinage.
- **Q5** : 35 des 40 « . » tirés dans le train ont une marque visible ; l'hypothèse de la décision 21 (« . » souvent sans encre) n'est pas confirmée.
- **Q3** : les points rouges de Doc 2937 restent visibles dans l'image reçue par le modèle ; F8 (lag 5) n'en lit que 5 sur 35, souvent remplacés par ه : les oublis relèvent de la lecture, pas de l'image.
- **Q4** : dans 11 des 18 confusions ي → ى tirées dans Doc 2937, deux points sont visibles sous la fin du mot ; convention différente entre Doc 2937 (ي 209, ى 106 en fin de mot) et Doc 2939 (ى 375, ي 4).
- **Q1** : environ 79 % du gain de F8 (lag 5) sur le test interne vient des catégories de lecture des lettres (67 % en validation), environ 21 % des espaces, environ 1 % des conventions au sens strict ; les catégories automatiques ne sont justes que pour les erreurs isolées (accord 0,37 brut, 0,32 pondéré) : ce sont des ordres de grandeur.
- **Q6** : Doc 3179, pire manuscrit du test interne (49,5 %), a une encre dégradée sur presque toute sa page ; aucune cause établie sur ses 13 lignes.

## 7. Limites et questions ouvertes

- **Poids de *Revnaḳ-ı Būstān*** : environ 63 % des lignes d'entraînement (1 755 / 2 771), surtout Doc 3263. Expérience possible plus tard pour limiter sa part.
- **Écart d'écriture** : l'entraînement est 100 % naskh, alors que 10 des 17 manuscrits du test interne ne le sont pas (divani, ta'liq, nastaliq, riq'a, mixtes). Le CER global du test interne mélangera la performance sur le naskh et la capacité à généraliser à d'autres écritures ; d'où le CER par écriture.
- **Couche `gen2-print`** : 18 pages (Doc 83, Doc 6398) pré-transcrites par un modèle puis corrigées, sans documentation (décision 4). Indice : leur texte est le seul en NFD, comme la sortie des modèles OpenITI (décision 16). Qualité de la correction inconnue, effet à tester.
- **Doc 86 et Doc 89** : même cote, dates différentes ; traités comme un seul manuscrit (décision 3).
- **Relecture** : toutes les pages Research n'ont été relues qu'une fois, donc sont moins fiables que les pages relues deux fois.
- **Conventions de transcription** inégales selon les transcripteurs d'après l'article JOHD. `normalize` corrige les différences d'encodage (ک / ك, ی / ي ى, voyelles), mais pas les choix de lecture (hamza sur yāʾ gardée ou non, kāf / gāf).
- **Lettres sans points** (ڡ, ٮ, ں) : transcription diplomatique de Doc 3178 (test interne), absente de l'entraînement. Ces lignes seront probablement pénalisées.
- **Caractères rares** (F13, Q7, descriptif) : 8 caractères du train n'apparaissent jamais dans la validation (، U+0655 ٠ ١ ٥ ژ ڭ گ), donc ne sont pas mesurés pendant le réglage ; 12 caractères du test interne sont absents du train (chiffres, ٮ ڡ ں ە, ZWNJ), dont ٮ, ڡ et ZWNJ hors codec, impossibles à écrire. Sur le test interne, en descriptif, F8 (lag 5) lit moins de chiffres que la baseline (6 sur 43 contre 18 sur 43 ; 4 manuscrits, dont 33 chiffres dans Doc 3215) et pas mieux la virgule arabe (0 sur 36 contre 1). Hypothèse, non établie (effectifs petits) : oubli d'une capacité du modèle de départ, les chiffres étant rares dans le train (4 occurrences). Pistes pour F15, rien n'est appliqué : ، souvent lue ه (lien possible avec les séparateurs, Q3 et Q5) ; ە presque toujours supprimée (convention possible). `reports/f13/q7_caracteres/`.
- **Unicode** : MAKHZAN est en NFC, le modèle de départ en NFD ; résolu par `normalize` (décision 5).
- **Conventions d'encodage du modèle de départ** : il écrit ی et ک (imprimé OpenITI) là où MAKHZAN écrit ي/ى et ك. Sans les règles 4 et 5, sa baseline serait pénalisée d'environ 8 points (décision 29) ; tout CER calculé sans `normalize`, comme celui de `ketos test`, n'est pas comparable.
- **Peu de données** : 2 757 lignes d'entraînement compilées.
- **CER de reconnaissance seule** : mesuré sur la segmentation de la vérité terrain (décision 31), il est plus bas que celui d'une chaîne complète sur une page brute.
- **Origine du gain de F9 non établie** : une partie peut venir de l'adoption des conventions de transcription de MAKHZAN (espaces, séparateurs, choix de lettres) plutôt que d'une meilleure lecture ; le gain presque uniforme entre écritures invite à le mesurer. F13 (Q1) : environ 79 % du gain sur le test interne vient des catégories de lecture des lettres, sous deux regroupements ; mais les catégories automatiques ne sont justes que pour les erreurs isolées, et la part des espaces (environ 21 %) ne sépare pas convention et lecture sans image : ordres de grandeur.
- **Comparaisons de F12 limitées** (SYNTHESE_F12.md) : validation de 2 manuscrits, 100 % naskh, avec un bootstrap par page un peu optimiste ; un seul entraînement par variante ; plafond de 150 époques atteint en progrès par B, C et les seeds 43 et 44 de la référence ; tous les entraînements sur un seul Mac, reproductibilité non vérifiée sur une autre machine.
- **Test interne clos** (décision 39) : les modèles suivants (F12, F15) ne pourront être comparés à F8 que sur la validation, et sur un jeu externe seulement en F15, si une réponse tardive en fournit un, avec un pré-enregistrement committé avant toute utilisation (décision 41 ; F11 clos le 2026-10-20).
- **Écart de 2 caractères** entre `ketos test` (21 209) et `evaluate` (21 211) sur le test interne, expliqué en F13 (Q2) : le réordonnancement BiDi de kraken (`--reorder`) retire les 2 ZWNJ de la vérité terrain (2 lignes de Doc 3215), qu'`evaluate` compte ; aucun écart sur la validation, qui n'a pas de ZWNJ. `evaluate` reste le CER de référence (décision 29). Reste un écart de 5 erreurs (5 580 contre 5 585, 0,02 point), dont au plus 2 dues aux ZWNJ, le reste probablement à l'alignement : non vérifiable sans relancer `ketos test` sur le test interne, interdit par la décision 39.
- **Analyse d'erreurs de F13** (SYNTHESE_F13.md) : un seul lecteur, qui ne lit pas l'ottoman ; échantillons de 10 à 40 entrées (13 lignes en Q6) ; emplacements estimés ; critères parfois précisés pendant la lecture, lecture de Q1 aidée par le chat Claude du projet ; le modèle de départ a été chargé pour lire son codec (sans prédiction) par plusieurs modules, dont `ketos_char_count` sur le test interne (Q2) ; corrigé en F14 : le codec est lu dans `reports/codec_modele_depart.json`, sans charger le modèle, aucun effet sur les chiffres de F7 à F9 (vérifié, ticket F14).
- **Ventilations du test interne** : écriture et relecture se recouvrent (manuscrits différents dans chaque groupe) et la plupart des écritures n'ont que 1 ou 2 manuscrits, sans intervalle. Ces écarts sont des indications, pas des effets démontrés.
- **Drapeau « anciens polygones »** : kraken 7.1.1 le perd en convertissant le modèle entraîné ; `predict` impose la découpe du projet (décision 36) ; corrigé dans le modèle publié en F14, qui porte le bon drapeau (décision 45).
- **Durée d'entraînement** : 4 h 38 pour F8 sur MacBook Air (MPS), dont 7 min de chargement par lancement ; les époques ont ralenti de 111 à 151 s après la première, cause non établie.
- **Outil** : la sortie texte de `kraken ocr` 7.1.1 est inversée sur nos ALTO ; les prédictions passent par l'API Python ou `ketos test` (skill kraken).
- **Pas de test d'une autre provenance** (décision 41) : la généralisation n'est mesurée que sur le test interne, qui vient du même jeu que l'entraînement (MAKHZAN) : mêmes conventions de transcription, même plateforme d'annotation, même équipe de curation. Il ne dit rien de la robustesse à d'autres conventions ni à d'autres fonds. Aucun jeu ouvert ne remplit les critères d'un test externe au 2026-09-28 (DATASETS.md) : Akis est en alphabet latin et imprimé (décision 40) ; le jeu rik'a d'Osmanlica.com n'a pas de licence et sa vérité terrain n'est pas documentée ; le sous-ensemble ottoman de CHURRO ne compte qu'un manuscrit, sans découpage en lignes. F11 est clos le 2026-10-20 sans jeu externe, faute de réponse ; la limite demeure ; une réponse tardive éventuelle alimenterait F15, avec un pré-enregistrement committé avant toute utilisation.
- **Modèle de départ** entraîné sur de l'imprimé, pas sur des manuscrits. Son codec couvre 99,92 à 100 % des caractères de MAKHZAN après normalisation ; restent inconnus `#` et ZWNJ (train, décision 23) et les lettres sans points de Doc 3178 (décision 24).

## 8. Prochaines étapes

Voir [ROADMAP.md](ROADMAP.md). F10 terminé : aucun jeu externe retenu (décisions 40 et 41). F11 clos le 2026-10-20 sans jeu externe (aucune réponse d'Osmanlica.com ni des auteurs de CHURRO), il ne sera pas rouvert ; une réponse tardive éventuelle alimenterait F15, avec un pré-enregistrement committé avant toute utilisation. F12 terminé (2026-10-19) : bruit mesuré (lag 5, puis lag 15 avec plafond 150, S = 0,5 point) et trois variantes comparées à F8 lag 15 seed 42 ; aucune n'est établie meilleure (B et A : pas de différence établie ; C : régression) ; synthèse dans [SYNTHESE_F12.md](SYNTHESE_F12.md). Modèle publié en F14 : F8 (lag 5), décision 44. F13 terminé (2026-10-20) : analyse d'erreurs descriptive en sept questions (Q1 à Q7), synthèse dans [SYNTHESE_F13.md](SYNTHESE_F13.md), pistes reportées dans le ticket F15. F14 en cours (2026-10-20) : modèle publié `ota_naskh_makhzan_v0.1.0` (F8, drapeau « anciens polygones » corrigé dans l'en-tête, poids et prédictions de la validation identiques à l'octet, décision 45), carte du modèle [MODEL_CARD.md](MODEL_CARD.md), licences (code MIT, contenus dérivés de MAKHZAN sous CC BY-NC-SA 4.0, [reports/LICENCE.md](reports/LICENCE.md)) ; reste la publication (GitHub, Zenodo) par l'utilisateur.

Journal des décisions : [DECISIONS.md](DECISIONS.md).
