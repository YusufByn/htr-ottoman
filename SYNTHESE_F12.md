# Synthèse de F12 : expériences complémentaires sur la validation

État au 2026-10-19. Sources : EXPERIMENTS.md, DECISIONS.md (décisions 42 à 44), `reports/bruit/`, `reports/comparaisons/`, `reports/training/`. Validation seulement : le test interne est clos (décision 39) et n'a pas été consulté.

Nommage : « F8 (lag 5) » désigne le modèle d'origine de F8 (arrêt anticipé après 5 époques sans progrès, seed 42, `models/f8_finetune/best_0.8365.safetensors`) ; « F8 lag 15 » désigne la référence de F12 (décision 43).

## 1. Objectif et règle de comparaison

F12 cherche si une modification simple de l'affinage de F8 (lag 5) améliore le CER de validation. Trois variantes ont été fixées avant tout entraînement (décision 42) et chacune ne change qu'une seule chose :

- **B** : augmentation d'images ;
- **A** : taux d'apprentissage de 3e-4 au lieu de 1e-4 ;
- **C** : entraînement sans les 18 pages en couche gen2.

Chaque variante est comparée à la même référence, jamais à la meilleure variante précédente.

La règle (décision 42) est appliquée par `compare_variant`. La différence est le CER de la variante moins celui de la référence, calculé par `evaluate`.

- La variante est **meilleure** si les trois conditions sont remplies : (a) la différence est sous −S ; (b) l'IC 95 % du bootstrap apparié par page (19 pages, 1 000 tirages, seed 42) est entièrement sous 0 ; (c) le CER baisse sur Doc 2937 et sur Doc 2939.
- C'est une **régression** si les trois conditions sont remplies dans l'autre sens.
- Sinon, il n'y a **pas de différence établie** : la règle ne permet pas de conclure, ce qui ne veut pas dire que l'effet est nul.
- S = max(0,5 point ; 2 × (CER max moins CER min) des trois seeds de la référence).

## 2. Mesure du bruit et règle d'arrêt

**Lag 5.** F8 (lag 5) a été relancé à l'identique avec les seeds 43 et 44. CER de validation des seeds 42, 43 et 44 : 16,32 / 16,84 / 17,75 %. Écart 1,43 point, d'où S = 2,86 points (`reports/bruit/f8_finetune/`).

**Diagnostic.** À époque égale, les trois courbes restent à 0,2 à 0,4 point l'une de l'autre (CER kraken), du même ordre que les oscillations d'une époque à l'autre. L'écart final vient surtout du moment où l'arrêt anticipé s'est déclenché : époque 49 pour la seed 44, 76 pour la seed 43, 91 pour la seed 42, alors qu'elles pouvaient encore progresser, comme l'ont montré les runs en lag 15. Un S de 2,86 points aurait masqué presque tout effet réel (`analysis.seed_curves`, `reports/figures/f12_bruit_seeds.png`).

**Décision 43.** Toute F12 passe à une nouvelle règle d'arrêt : lag 15 et plafond de 150 époques. Le plafond est appliqué par `ketos_capped`, car kraken 7.1.1 l'ignore quand l'arrêt anticipé est actif. La nouvelle référence est « F8 lag 15 », entraînée avec les seeds 42, 43 et 44 ; la règle de comparaison et ses critères ne changent pas. Contrôle : la seed 42 reproduit F8 (lag 5) aux 6 décimales sur ses 91 premières époques.

**Nouveau S.**

- CER des seeds 42, 43 et 44 : 15,60 / 15,58 / 15,40 %, soit 3 338 / 3 334 / 3 294 erreurs sur 21 393 caractères.
- Écart 0,21 point (44 erreurs), 2 × écart 0,41 point : **S = 0,5 point**, le plancher s'applique.
- Seed 42 : 150 époques, meilleure 135, arrêt « lag et plafond ». Seeds 43 et 44 : coupées par le plafond alors qu'elles progressaient (meilleures époques 149 et 150).
- En nombre d'erreurs : une variante est meilleure à 3 231 erreurs au plus ; c'est une régression à 3 445 erreurs au moins.

## 3. Contrôles

Pour chacune des trois variantes (détail dans EXPERIMENTS.md) :

- **Déterminisme** : l'époque 1 du run est identique à celle de son essai technique (`analysis.same_curve --until 1`, perte et précision de validation, écart 0).
- **Meilleur modèle** : les 34 tenseurs de `best_*.safetensors` sont identiques à ceux du checkpoint de la meilleure époque et diffèrent de ceux des autres checkpoints gardés.
- **Prédiction** : refaite avec le chemin explicite du meilleur modèle, identique octet pour octet à celle de `reports/`.
- **Écart kraken / `evaluate`** : 15 erreurs au plus (B 3, A 6, C 15).
- **Comparabilité** : même règle d'arrêt que la référence (lag 15, plafond 150, min-epochs 5) et même lanceur (`ketos_capped`), vérifiés par `compare_variant` (pour B, lanceur vérifié lors de la relance de la comparaison, c0c62eb, résultats identiques).
- **kraken** : aucune ligne remplacée, aucun avertissement du mode déterministe.

Le déterminisme est établi sur une seule machine (MacBook Air, MPS). Les ralentissements constatés pendant les runs de B et de A, et les mises en veille de macOS pendant celui de C, n'ont ajouté que du temps : aucun calcul ne dépend de la durée.

## 4. Résultats

Référence : F8 lag 15 seed 42, 15,60 % (3 338 erreurs) ; Doc 2937 16,42 % (1 567), Doc 2939 14,95 % (1 771).

| Variante | CER val | Erreurs | Différence | Doc 2937 | Doc 2939 | Meilleure époque / dernière, arrêt | (a) | (b) IC 95 % | (c) | Verdict | Commit du run / comparaison |
|---|---:|---:|---|---|---|---|---|---|---|---|---|
| B augmentation | 15,36 % | 3 285 | −0,25 point (−53) | 16,00 % (−40) | 14,84 % (−13) | 147 / 150, plafond | non | non, [−0,54 ; +0,12] | oui, baisse | pas de différence établie | 7834e22 / 6b4b660 |
| A taux 3e-4 | 15,14 % | 3 239 | −0,46 point (−99) | 15,84 % (−55) | 14,58 % (−44) | 72 / 87, lag | non, 8 erreurs de trop | oui, [−0,78 ; −0,12] | oui, baisse | pas de différence établie | 97a0be3 / e529342 |
| C sans gen2 | 16,17 % | 3 459 | +0,57 point (+121) | 16,79 % (+36) | 15,67 % (+85) | 145 / 150, plafond | oui, 14 erreurs au-delà du seuil | oui, [+0,23 ; +0,90] | oui, hausse | régression | ff41dbe / 1372fe5 |

Pour B et A, (a), (b) et (c) sont donnés dans le sens du gain, et aucune condition de régression n'est remplie. Pour C, ils sont donnés dans le sens de la régression, et aucune condition de gain n'est remplie. Différences exactes : B −0,248, A −0,463, C +0,566 point. Le commit du run est celui de `models/<variante>/run.json`. Détail : `reports/comparaisons/<variante>_f8_lag15_seed42/val/`.

## 5. Lecture descriptive

**B (augmentation).**

- Le CER baisse dans les deux manuscrits, mais la différence ne vaut que la moitié de S et l'IC contient 0.
- B a été coupée par le plafond alors qu'elle battait encore des records (jusqu'à l'époque 147).

**A (taux 3e-4).**

- C'est le seul run de F12 arrêté par le lag avant le plafond : 87 époques, meilleure 72, contre 135 pour la référence.
- (b) et (c) sont remplies. (a) ne l'est pas, à 8 erreurs près : 3 239 contre 3 231 au plus.
- La perte d'entraînement baisse jusqu'à la dernière époque, pendant que la précision de validation stagne (0,8437 à 0,8487 sur les époques 73 à 87).

**C (sans gen2).**

- Le CER monte dans les deux manuscrits, davantage sur Doc 2939 (+0,72 point contre +0,38). Les trois conditions de régression sont remplies.
- Le jeu de C n'est pas seulement privé de la couche gen2. Il perd aussi 254 lignes sur 2 757 (9,2 %), deux manuscrits entiers (Doc 83 et 6398) et 16 pas d'optimisation par époque (157 contre 173). Le verdict porte sur ce jeu réduit dans son ensemble, pas sur les pages gen2 seules.
- C a été coupée par le plafond alors qu'elle progressait encore (records jusqu'à l'époque 145).

## 6. Limites

- **Validation étroite** : 2 manuscrits d'une seule œuvre (*Manāfi' al-nās*), 100 % naskh, 412 lignes. Un effet sur d'autres écritures ou d'autres mains ne serait pas vu, et la condition (c) repose sur deux mains seulement.
- **Bootstrap par page optimiste** : les 19 pages viennent de 2 manuscrits et se ressemblent, donc l'IC est un peu trop étroit, d'où le seuil S. Un bootstrap par manuscrit est impossible avec 2 manuscrits (décision 30).
- **Un seul entraînement par variante** ; le bruit lui-même repose sur 3 entraînements de la référence.
- **Plafond de 150 époques** : B et C ont été coupées alors qu'elles progressaient (records aux époques 147 et 145), comme les seeds 43 et 44 de la référence (149 et 150). La seed 42 s'est arrêtée par le lag pile au plafond (meilleure 135). Les comparaisons portent donc sur des modèles à 150 époques au plus, pas sur des modèles qui ont fini de progresser.
- **S mesuré à 150 époques** : l'écart de 0,21 point entre seeds mesure le bruit à ce plafond, pas en fin de progression. Tant que l'écart reste sous 0,25 point, S vaut le plancher.
- **Effets mélangés dans C** : moins de lignes, moins de manuscrits et moins de pas d'optimisation, en même temps que le retrait de la couche gen2 (décision 42, limite 5).
- **Caractères non mesurés** :
  - la validation ne contient que 38 caractères distincts ;
  - ٠ ڭ ، ٥ ١ ژ n'apparaissent qu'à l'entraînement et ne comptent donc pas dans la précision de validation (`ketos.log`) ; pour la référence, B et A, c'est aussi le cas de گ et de U+0655 ;
  - C ne voit plus du tout گ ni U+0655 à l'entraînement : l'effet n'est pas mesurable ici.
- **Meilleure époque choisie sur la validation** (décision 35) : chaque CER est un peu optimiste, de la même façon pour tous.
- **Comparaisons multiples** : trois variantes comparées sans correction (décision 42).
- **F8 lag 15 contre F8 (lag 5)** : le gain de F8 lag 15 sur F8 (lag 5), 15,60 % contre 16,32 %, est descriptif ; il n'est jamais passé par la règle (décision 44).
- **Tous les entraînements sur un seul Mac** : la reproductibilité n'est pas vérifiée sur une autre machine.

## 7. Apports pour F15 (pistes)

- **Point de départ** : F8 lag 15 seed 42 (décision 44). Il n'est pas publié et n'a aucune mesure sur le test ; F15 aura son propre test réservé, constitué avant tout entraînement.
- **Règle d'arrêt** : le lag 15 a stabilisé le bruit. En revanche, le plafond de 150 époques a coupé 4 des 6 runs en lag 15 alors qu'ils progressaient : un plafond plus haut, ou une autre durée, serait à fixer avant les runs de F15.
- **Taux 3e-4** : meilleur score atteint en 72 époques au lieu de 135, pour un CER que la règle ne distingue pas de la référence. C'est une piste pour raccourcir les entraînements, sans gain établi.
- **Augmentation** : effet non établi sur cette validation ; à reprendre avec une validation plus large.
- **Pages gen2** : les retirer, avec la baisse de volume que cela entraîne, donne une régression. Pour isoler la couche gen2, il faudrait une expérience témoin qui retire autant de lignes hors gen2.
- **Mesure** :
  - une validation avec plus de manuscrits et d'autres écritures permettrait un bootstrap par manuscrit et rendrait la condition (c) plus exigeante ;
  - plusieurs seeds par variante réduiraient l'incertitude liée à un entraînement unique.
- **Données** : ACDC-Training (décision 42), RASAM et TariMa (DATASETS.md) sont réservés à l'entraînement de F15.
- **Rappel de la décision 44** : le modèle publié en F14 est F8 (lag 5, seed 42, époque 86), le seul modèle affiné évalué sur le test interne (CER 26,3 %).
