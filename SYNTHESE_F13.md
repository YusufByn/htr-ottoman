# Synthèse de F13 : analyse d'erreurs

État au 2026-10-20. Sources : EXPERIMENTS.md, ROADMAP.md (ticket F13 : plan, précisions et compléments datés), DECISIONS.md (décision 39 et ses compléments du 2026-10-19 et du 2026-10-20), `reports/f13/`.

Nommage : « F8 (lag 5) » désigne le modèle d'origine de F8 (`models/f8_finetune/best_0.8365.safetensors`), le seul modèle affiné évalué sur le test interne ; « F8 lag 15 » désigne la référence de F12 (décision 43). « Baseline » désigne le modèle de départ OpenITI sans affinage.

## 1. Objet et règles

F13 décrit les erreurs des modèles déjà évalués, sur les prédictions déjà sauvegardées, en sept questions (Q1 à Q7, plan fixé le 2026-10-19 avant toute analyse, 124a7c8). Règles suivies :

- **Descriptif seulement** : ni choix de modèle, ni réglage, ni règle de normalisation ou de données ; une règle suggérée devient une décision pour F15, jamais appliquée aux chiffres de F9. Ni IC ni verdict.
- **Lecture humaine** : un échantillon tiré avec la seed 42, une page HTML autonome, un CSV de jugements versionné tel quel avant toute analyse. Lecture à l'aveugle (ni prédiction, ni erreur, ni CER affichés) pour Q3, Q4, Q5 et Q6 ; Q1 juge le texte, modèle et catégorie affichés, comme le prévoit le plan. Les critères sont écrits et commités avant la lecture ; les précisions prises pendant la lecture sont ajoutées par des compléments datés, sans modifier les fichiers de jugements.
- **Test interne en mode exploratoire** (décision 39 inchangée) : complément du 2026-10-19 (mode exploratoire d'`error_analysis`, option explicite, seuls les `lignes.parquet` de F9, SHA-256 vérifiés, jamais `predict`, sorties sous `reports/f13/` avec la mention « exploratoire, décision 39 ») ; complément du 2026-10-20 (98f8e89, précisé en d4b3280 : images des lignes de Doc 3179 pour Q6 seulement, aucune prédiction, aucun modèle chargé). Q1 n'affiche aucune image du test interne (9563904).

## 2. Résultats par question

Ordre suivi : Q2, Q7, Q5, Q3, Q4, Q1, Q6.

**Q2, écart `ketos test` / `evaluate`** (conclusion 20e8e2b, limite 4646d99).
- Observé : les 2 caractères d'écart sur le test interne (21 209 contre 21 211) sont 2 ZWNJ de Doc 3215, retirés par le réordonnancement BiDi de kraken ; aucun écart sur la validation.
- Non expliqué : 5 erreurs de moins pour `ketos test` (0,02 point), au plus 2 dues aux ZWNJ ; le reste vient probablement de l'alignement, non vérifiable sans nouvelle prédiction.

**Q7, caractères rares** (38225a5, 5a91fec).
- Observé : 8 caractères du train absents de la validation ; 12 caractères du test interne absents du train, dont ٮ, ڡ et ZWNJ hors codec. Sur le test interne, F8 (lag 5) lit 6 chiffres sur 43 (baseline 18), 0 virgule ، sur 36 (baseline 1).
- Hypothèse non établie : oubli par l'affinage, les chiffres étant rares dans le train (4).

**Q5, « . » sans encre dans le train** (013367f).
- Observé : 35 des 40 « . » tirés dans le train ont une marque visible (lecture 2 : 35 oui, 1 non, 4 incertain) ; sur la validation, F8 (lag 5) oublie 97 « . » sur 123.
- L'hypothèse de la décision 21 (« . » souvent sans encre) n'est pas confirmée sur cet échantillon.

**Q3, encre rouge en niveaux de gris** (04f9e98).
- Observé : les 37 points rouges présents en couleur restent visibles dans l'image reçue par le modèle ; F8 (lag 5) n'en lit que 5 sur 35 nettement visibles, il supprime les autres ou les remplace, souvent par ه. Poids : environ 0,46 point de CER sur la validation.
- Les oublis relèvent de la lecture, pas de l'image.

**Q4, ي et ى de fin de mot dans Doc 2937** (6736239).
- Observé : deux points vus sous la fin du mot dans 11 des 18 confusions ي → ى tirées (aucun point vu dans 1 à 4 selon la lecture) ; points vus sous 3 des 10 ى lus ى ; estimation pondérée de 0,60 avec points vus pour les 280 fins de mot. Écart de convention : 2937 écrit ي 209 fois et ى 106 fois en fin de mot, 2939 écrit ى 375 fois et ي 4 fois.
- Seuls les « oui » sont stables sous les trois lectures ; le reste dépend de la lecture retenue.

**Q1, conventions contre lecture** (d1d9526, référence précisée 5c31a2f).
- Observé : sous les deux regroupements, environ 79 % du gain de F8 (lag 5) sur le test interne vient des catégories de lecture des lettres (67 % en validation) ; conventions au sens strict environ 1 % (3 %) ; espaces environ 21 % (30 %). Taux d'accord des catégories automatiques : 0,37 brut, 0,32 pondéré ; élevé seulement pour chiffre, même squelette et ي / ى.
- Les catégories ne sont validées que pour les erreurs isolées : les décompositions par catégorie restent des ordres de grandeur. La part « conventions » prise globalement dépend du rangement des espaces et n'est pas retenue.

**Q6, Doc 3179** (6c08707).
- Observé : pire manuscrit du test interne sous F8 (lag 5) (49,5 %, baseline 56,5 %), l'un des plus petits gains (−7,0 points) ; surtout des erreurs de lettres ; encre pâle, effacée ou tachée sur 10 lignes sur 13 ; aucune lettre coupée, aucun morceau d'autre ligne, aucun ajout, aucune ligne inclinée vus.
- Aucune cause établie : l'état de l'encre touche presque toute la page, et la part de l'écriture (naskh et chikasté) reste non mesurée.

## 3. Hypothèses écartées

- **Décision 21, « . » du train souvent sans encre** (Q5, 013367f) : non confirmée ; un seul « . » sans marque sur 40.
- **Encre rouge invisible en niveaux de gris** (Q3, 04f9e98) : non confirmée ; aucun point présent en couleur et invisible en gris.

Ensemble, ils orientent les oublis de « . » vers la lecture du modèle ; seul Q3 le montre directement, sur Doc 2937.

## 4. Écarts et corrections en cours de route

- **Modèle de départ chargé pour lire son codec**, sans aucune prédiction : en Q2 (vérité terrain du test interne, via `prepare.select_lines`, documenté en 11b9416) et lors d'une première génération de la page de Q6 (régénérée avec le chargement de modèle interdit, fichiers identiques à l'octet, 5236bc4). Q1 et Q7 ne le chargent pas. Option `select_lines(with_codec=False)` ajoutée. Pour être complet : `period_ink`, `red_ink`, `final_ya` et `final_ya_errors` chargent le modèle de départ de la même façon sur le train et la validation, hors décision 39 (11b9416).
- **Lecture de Q1 aidée** par le chat Claude du projet sur toutes les entrées (règle mécanique appliquée ensemble ; pas à l'aveugle, comme prévu), premières réponses changées après ses remarques (7c2a99d).
- **Q6** : critères précisés par le chat Claude du projet pendant la lecture, après la première entrée ; une capture de q6_01 lui a été envoyée ; il n'a donné aucun jugement (c8080e6, ec84d0b).
- **Réponses changées pendant la lecture** : q6_01, 5 réponses sur 6 changées après la précision des critères, dont D et E qui entrent dans le croisement (c8080e6, corrigé en ec84d0b). En Q3, la question couleur a d'abord été comprise autrement ; les réponses couleur concernées ont été corrigées, les réponses en gris étaient verrouillées (ROADMAP, précision de Q3).
- **Règles fixées après avoir vu des tableaux**, signalées et soumises à un contrôle de sensibilité : lecture 3 de Q4 ; tableau 5 de Q1 et sa variante ; regroupement de la précision du 2026-10-20 de Q1, choisi après avoir vu les comptes par catégorie (aucune ligne), rapporté à côté de celui du plan (3e85d24).
- **Tirage de 30 lignes impossible en Q6** : Doc 3179 n'a que 13 lignes gardées, prises en entier (d4b3280) ; le chiffre de 30 avait été fixé sans vérifier la taille de la population.
- **Corrections faites en vérifiant les fichiers** : en Q1, liste des entrées non indépendantes (27 entrées sur 13 lignes, d'après `echantillon.csv`) et q1_097 (vérité terrain non vide, fenêtre faite d'insertions) (7c2a99d) ; en Q6, gain de Doc 3179 (l'un des plus petits, pas le plus petit) avant d'écrire la conclusion (6c08707) ; en Q1, référence des deux décompositions par catégorie (5c31a2f).
- **Non consigné jusqu'ici** : avant la lecture de Q5, une remarque sur les points rouges de Doc 2937 avait été faite par Claude Code (pas par le chat Claude du projet) dans la conversation ; elle a pu orienter l'attention vers les points rouges pendant la lecture de Q5. Aucun constat de visibilité n'a été communiqué avant la lecture de Q3.

## 5. Limites communes

- Un seul lecteur, qui ne lit pas l'ottoman : la transcription elle-même n'est jamais jugée ; les questions portent sur des formes et des marques visibles.
- Petits échantillons (10 à 40 entrées par question ou par case, 13 lignes en Q6), parfois concentrés dans un manuscrit ou une page ; entrées parfois non indépendantes (même ligne, même page).
- Emplacements estimés : boîtes placées d'après l'encre ou la position dans le texte, certaines décalées (option « boîte décalée » prévue).
- Un seul alignement retenu à coût égal ; catégories automatiques justes surtout pour les erreurs isolées (Q1).
- Validation de 2 manuscrits ; test interne consulté seulement en mode exploratoire, sur les prédictions de F9 (baseline et F8 (lag 5)).
- Critères précisés pendant certaines lectures (Q5, Q1, Q6), avec compléments datés.
- Descriptif seulement : aucun IC, aucun verdict, aucune règle appliquée.

## 6. Pistes

Les pistes issues de F13 sont reportées dans le ticket F15 de ROADMAP, section « Pistes issues de F13 » (398beb2), groupées par thème (données ; conventions et normalisation ; alignement et catégories ; relecture avec un lecteur de l'ottoman). Les pistes de F12 restent dans SYNTHESE_F12.md, section 7. Une ligne a été ajoutée au ticket F14 : lire le codec du modèle de départ sans le charger, dans tous les modules.

## 7. Commits de F13

Liste générée par `git log --reverse --format='%ad %h %s' --date=short 124a7c8^..398beb2` (43 commits).

| Date | Commit | Objet |
|---|---|---|
| 2026-10-19 | 124a7c8 | F13 : plan de l'analyse d'erreurs et complément à la décision 39 |
| 2026-10-19 | 4a6fc17 | F13 : échantillon de Q1 à 10 par catégorie, test du mode exploratoire précisé |
| 2026-10-19 | 20e8e2b | F13, Q2 : écart de caractères ketos test / evaluate expliqué |
| 2026-10-19 | 4646d99 | F13 : écart de 5 erreurs ketos test / evaluate noté comme limite |
| 2026-10-19 | 38225a5 | F13, Q7 : caractères du train absents de la validation, et du test interne absents du train |
| 2026-10-19 | 5a91fec | F13, Q7 : chiffres et pistes pour F15 notés (descriptif) |
| 2026-10-19 | 9669de0 | F13 : case pour reporter les pistes F15 à la fin du ticket |
| 2026-10-19 | 701bc4a | F13, Q5 : page de lecture à l'aveugle des « . » du train (avant lecture) |
| 2026-10-19 | 84b60a9 | F13, Q5 : répartition de l'échantillon consignée, consignes de lecture |
| 2026-10-19 | 8a57386 | F13, Q5 : lecture à l'aveugle de l'utilisateur (40 réponses) |
| 2026-10-19 | b9fb0c6 | F13, Q5 : « . » oubliés et ajoutés sur la validation |
| 2026-10-19 | 013367f | F13, Q5 terminée : deux lectures des jugements et conclusion |
| 2026-10-19 | 5070c60 | F13, Q3 : page de lecture à l'aveugle, gris puis couleur (avant lecture) |
| 2026-10-19 | 6bc8c08 | F13, Q3 : lecture à l'aveugle de l'utilisateur (40 entrées) |
| 2026-10-19 | 0a07445 | F13, Q3 : points rouges lus par les modèles, après la lecture |
| 2026-10-19 | 04f9e98 | F13, Q3 terminée : deux lectures des jugements et conclusion |
| 2026-10-19 | 4a26139 | F13, Q4 : page de lecture à l'aveugle, fins de mot ي / ى (avant lecture) |
| 2026-10-19 | 694fa66 | F13, Q4 : lecture à l'aveugle de l'utilisateur (40 réponses) |
| 2026-10-19 | 6736239 | F13, Q4 terminée : trois lectures, contrôle de sensibilité et conclusion |
| 2026-10-20 | c658ccb | F13, Q1, étape 1 : mode exploratoire du test interne dans error_analysis |
| 2026-10-20 | b4bdb1b | F13, Q1, étape 2 : mode exploratoire lancé sur le test interne |
| 2026-10-20 | 9563904 | F13, Q1 : précision du plan, fixée avant toute lecture |
| 2026-10-20 | b756474 | F13, Q1 : page de lecture, la catégorie automatique est-elle juste ? (avant lecture) |
| 2026-10-20 | 3e85d24 | F13, Q1 : rapport sous deux regroupements, ajouté avant la lecture |
| 2026-10-20 | 85ecff7 | F13, Q1 : lecture de l'utilisateur (100 réponses), déposée telle quelle |
| 2026-10-20 | 7c2a99d | F13, Q1 : précisions prises pendant la lecture (complément daté) |
| 2026-10-20 | e9c5b94 | F13, Q1 : précision (8) prise pendant la lecture, cas limite des chiffres |
| 2026-10-20 | 83e811d | F13, Q1 : taux d'accord par catégorie et sommes conventions / lecture (tableaux 1 à 4) |
| 2026-10-20 | 0f17955 | F13, Q1 : annexe, tableau 5, « non » ventilés par commentaire |
| 2026-10-20 | d1d9526 | F13, Q1 terminée : variante du tableau 5, note sur q1_097 et conclusion |
| 2026-10-20 | 5c31a2f | F13, Q1 : référence des deux décompositions par catégorie précisée |
| 2026-10-20 | 98f8e89 | Décision 39, complément du 2026-10-20 : images de Doc 3179 pour Q6 de F13 |
| 2026-10-20 | 6641756 | F13, Q6 : critères de lecture, fixés avant toute préparation |
| 2026-10-20 | 86a9a61 | F13, Q6 : précision, image 1 comme en Q3 et tableaux du plan après la lecture |
| 2026-10-20 | d4b3280 | F13, Q6 : les 13 lignes gardées de Doc 3179 prises en entier |
| 2026-10-20 | 5236bc4 | F13, Q6 : page de lecture à l'aveugle, Doc 3179 (avant lecture) |
| 2026-10-20 | 666e109 | F13, Q6 : lecture de l'utilisateur (13 lignes), déposée telle quelle |
| 2026-10-20 | c8080e6 | F13, Q6 : précisions prises pendant la lecture (complément daté) |
| 2026-10-20 | 11b9416 | F13, Q2 : chargement du modèle de départ pour lire son codec, documenté |
| 2026-10-20 | 1bc6c36 | F13, Q6 : tableaux du plan pour Doc 3179, après la lecture |
| 2026-10-20 | ec84d0b | F13, Q6 : correction de la limite du complément c8080e6 |
| 2026-10-20 | 6c08707 | F13, Q6 terminée : conclusion |
| 2026-10-20 | 398beb2 | F13 : pistes pour F15 reportées dans le ticket F15, ligne pour F14 |
