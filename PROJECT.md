# Projet HTR ottoman

Résumé du projet et état d'avancement. Mis à jour à chaque étape terminée.
Dernière mise à jour : 2026-09-28.

## 1. Résumé

Reconnaissance automatique d'écriture manuscrite (HTR) sur des manuscrits en turc ottoman, avec kraken.
On part d'un modèle entraîné sur de l'**imprimé** ottoman (OpenITI) et on l'affine sur les manuscrits ottomans de MAKHZAN.

**Question de recherche** : dans quelle mesure ce modèle affiné généralise-t-il à des manuscrits jamais vus, d'abord sur le test interne (ACDC-Evaluation), puis sur un jeu externe (Akis) ?

Projet de recherche et portfolio.

## 2. Données et modèle de départ

| Ressource | Version | Rôle | Licence |
|-----------|---------|------|---------|
| OpenITI MAKHZAN, partie ottomane | 2026.1.2, DOI 10.5281/zenodo.19861912 | entraînement, validation, test interne | CC BY-NC-SA 4.0 |
| Akis | à venir | test final externe | Apache 2.0, citer Tasdemir et al., DAS 2024 |
| Modèle OpenITI ottoman imprimé | DOI 10.5281/zenodo.7050342 (kraken, CER annoncé 4,22 %) | modèle de départ | CC0 |

Tout modèle dérivé de MAKHZAN est sous CC BY-NC-SA. Détails et MD5 : [README](README.md).

## 3. Protocole d'évaluation

| Jeu | Contenu | Manuscrits | Pages | Lignes transcrites | Décisions |
|-----|---------|-----------:|------:|-------------------:|-----------|
| Entraînement | Research, sauf l'œuvre de validation (6 œuvres) | 11 | 199 | 2 771 | 2, 3, 6 |
| Validation | *Manāfi' al-nās fī al-ṭibb* (Doc 2937, 2939) | 2 | 19 | 436 | 7 |
| Test interne | ACDC-Evaluation ottoman, jamais utilisé pour le réglage | 17 | 30 | 555 | 1 |
| Test final | Akis, évaluation finale uniquement | à venir | à venir | à venir | CLAUDE.md |

- Découpage par œuvre : toutes les copies d'une œuvre sont dans le même jeu (décision 6).
- Les lignes sans transcription sont exclues de l'entraînement.
- **Métrique** : CER (taux d'erreur par caractère), calculé en NFD sur vérité terrain et prédictions normalisées de la même façon (décision 5). Rapporté au global, par écriture et par catégorie de relecture.
- Les fichiers de `splits/` sont à venir.

## 4. Fonctionnalités

| Fonctionnalité | État |
|----------------|------|
| Vérification de l'environnement (kraken, MPS) : `scripts/check_mps.py` | fait |
| Inventaire des manuscrits ottomans : `analysis.inventory_ottoman` | fait |
| Comparaison Research / ACDC-Evaluation, par manuscrit et par œuvre : `analysis.compare_ottoman_sources` | fait |
| Téléchargement de MAKHZAN avec vérification MD5 (module) | à venir |
| Extraction des pages et des ALTO | à venir |
| Normalisation NFD et tests | à venir |
| Création des splits | à venir |
| Évaluation (CER par écriture et relecture) | à venir |
| Fine-tuning kraken | à venir |

## 5. État d'avancement

Voir [ROADMAP.md](ROADMAP.md) : liste des tickets F0 à F14, avec leurs dépendances et leur statut.

## 6. Résultats clés

À venir. Le détail de chaque expérience est consigné dans [EXPERIMENTS.md](EXPERIMENTS.md).

## 7. Limites et questions ouvertes

- **Poids de *Revnaḳ-ı Būstān*** : environ 63 % des lignes d'entraînement (1 755 / 2 771), surtout Doc 3263. Expérience possible plus tard pour limiter sa part.
- **Écart d'écriture** : l'entraînement est 100 % naskh, alors que 10 des 17 manuscrits du test interne ne le sont pas (divani, ta'liq, nastaliq, riq'a, mixtes). Le CER global du test interne mélangera la performance sur le naskh et la capacité à généraliser à d'autres écritures ; d'où le CER par écriture.
- **Couche `gen2-print`** : 18 pages (Doc 83, Doc 6398) probablement pré-transcrites par un modèle puis corrigées, sans documentation (décision 4). Effet à tester.
- **Doc 86 et Doc 89** : même cote, dates différentes ; traités comme un seul manuscrit (décision 3).
- **Relecture** : toutes les pages Research n'ont été relues qu'une fois, donc sont moins fiables que les pages relues deux fois.
- **Conventions de transcription** inégales selon les transcripteurs (hamza sur yāʾ, kāf / gāf) d'après l'article JOHD ; voyelles en général non transcrites.
- **Unicode** : MAKHZAN est en NFC, le modèle de départ en NFD (décision 5).
- **Peu de données** : environ 2 800 lignes d'entraînement.
- **Modèle de départ** entraîné sur de l'imprimé, pas sur des manuscrits.

## 8. Prochaines étapes

Voir [ROADMAP.md](ROADMAP.md). Les tickets sans dépendance restante sont F1 et F2.

Journal des décisions : [DECISIONS.md](DECISIONS.md).
