# Données ouvertes pour l'HTR ottoman manuscrit

État des jeux de vérité terrain disponibles pour la reconnaissance d'écriture manuscrite (HTR) en turc ottoman, établi pour choisir un jeu de test externe (ticket F10, décisions 40 et 41).

- **Date de la recherche** : 2026-09-28. Mails envoyés le même jour à Osmanlica.com et aux auteurs de CHURRO, réponses attendues (sections 3.3 et 3.4).
- **Méthode** : catalogues et moteurs de recherche des dépôts (HTR-United, Zenodo, Hugging Face, GitHub), fiches et métadonnées des jeux, courts extraits lus par les API (quelques lignes, quelques Ko). Seul Akis a été téléchargé et inventorié. Les autres jeux n'ont pas été téléchargés : leurs chiffres sont ceux que publient leurs auteurs, sauf mention contraire.
- **Conclusion** : à cette date, **aucun jeu ne remplit tous les critères** d'un test externe. Le seul jeu ouvert de manuscrits ottomans avec une vérité terrain par ligne en écriture arabe est OpenITI MAKHZAN, déjà utilisé par le projet pour l'entraînement, la validation et le test interne.

## 1. Critères

Un jeu de test externe doit, pour ce projet :

1. contenir des **manuscrits** en turc ottoman ;
2. avoir une vérité terrain en **écriture arabe**, faite par des humains (pas une sortie de modèle, pas une translittération latine) ;
3. être sous **licence ouverte**, permettant au moins l'évaluation et la publication des scores ;
4. avoir une **provenance distincte de MAKHZAN** (ni les mêmes manuscrits, ni les mêmes œuvres) ;
5. être **absent des données d'entraînement du modèle de départ** (OpenITI, ottoman imprimé, DOI 10.5281/zenodo.7050342) ;
6. compter **au moins quelques centaines de lignes**, idéalement de plusieurs manuscrits (intervalle de confiance par manuscrit, décision 30) ;
7. idéalement, fournir des **pages avec lignes de base** (ALTO ou PAGE), pour découper les lignes comme pour MAKHZAN (décisions 25 et 31).

Contraintes du projet : un jeu retenu comme test ne pourra plus jamais servir à l'entraînement. RASAM et TariMa sont réservés à l'entraînement de F15.

## 2. Vue d'ensemble

Critères : 1 manuscrit ottoman, 2 vérité terrain humaine en écriture arabe, 3 licence ouverte, 4 provenance distincte de MAKHZAN, 5 absent du modèle de départ, 6 taille, 7 lignes de base. « ? » : non indiqué par la source.

| Jeu | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Verdict |
|-----|---|---|---|---|---|---|---|---------|
| OpenITI MAKHZAN (partie ottomane) | oui | oui | oui | sans objet | oui | oui | oui | déjà utilisé (entraînement, validation, test interne) |
| Akis, jeu de test public | non (imprimé) | non (latin) | oui | oui | ? | oui | non | exclu (décision 40) |
| `asparius/ottoman-ocr-8k` | non | non | ? | oui | ? | oui | non | exclu : Akis reconditionné |
| Osmanlica.com, jeu rik'a | oui | ? | non | ? | oui | oui | non | le plus proche ; réponse attendue |
| CHURRO, mémoires d'Osman Ağa | oui | texte de l'édition Kreutel (1980), fidélité à la page à confirmer | sources contradictoires | oui | oui | un seul manuscrit | non | le plus proche ; réponse attendue |
| RikaOCR, données BOA | oui | oui | non | oui | oui | 132 lignes de test | ? | exclu : pas de licence des données |
| OtaHTR-search | oui | non (sortie de modèle) | oui (CC0) | oui | oui | oui | oui (polygones) | exclu : pas de vérité terrain |
| OpenITI `arabic_ms_data` | oui | non (pas de texte) | non | ? | oui | 10 pages | oui | exclu : segmentation seule |
| Registre de population BOA (Hugging Face) | oui | mêlée de turc moderne | oui (CC BY) | oui | oui | non (8 images) | non | exclu : trop petit, texte par page |
| RASAM, TariMa | non (arabe maghrébin) | oui | oui | oui | oui | oui | oui | exclus : pas ottoman ; réservés à F15 |

## 3. Candidats examinés

### 3.1 OpenITI MAKHZAN, partie ottomane (référence)

- **Source** : Zenodo, DOI 10.5281/zenodo.19861912, version 2026.1.2 ; Allen et al., *Journal of Open Humanities Data*.
- **Contenu** : 30 manuscrits ottomans, 248 pages, 3 868 lignes dont 3 762 transcrites (inventaire du projet), plusieurs écritures (naskh, divani, ta'liq, nastaliq, riq'a, mixtes).
- **Vérité terrain** : écriture arabe, ALTO v4 avec lignes de base et polygones (eScriptorium). Licence CC BY-NC-SA 4.0.
- **Usage dans le projet** : `Research` pour l'entraînement et la validation, `ACDC-Evaluation` pour le test interne (décision 1), clos depuis F9 (décision 39).

### 3.2 Akis, jeu de test public (Tasdemir et al., DAS 2024)

- **Source** : GitHub `verimsu/Akis-Ottoman-Dataset`, commit `c7a6e5b` (2024-09-14), zip stocké avec git LFS (584 379 296 octets). Licence Apache 2.0.
- **Contenu** (inventaire du projet, `reports/akis_sources.csv`) : 8 036 images de lignes de 13 livres **imprimés** (1732 à 1927, 3 179 pages), naskh typographique, lignes déjà découpées à 64 px de haut.
- **Vérité terrain** : **alphabet latin** (turc moderne), aucune lettre arabe ; encodage mêlant NFC et NFD.
- **Raison de l'exclusion** : la translittération latine ne se convertit pas de façon fiable en écriture arabe (une lettre latine correspond à plusieurs lettres arabes ; voyelles ajoutées, suffixes modernisés, découpage des mots différent) ; et ce sont des imprimés. Détail et exemples : décision 40.
- **Copies** : `OttomanNLP/Akis-Ottoman-Dataset` (Hugging Face) ; `asparius/ottoman-ocr-8k` (Hugging Face, sans licence, 7 232 + 804 = 8 036 exemples pour 583 Mo, texte latin : très probablement Akis redécoupé en train et test).

### 3.3 Osmanlica.com, jeu manuscrit rik'a

- **Source** : osmanlica.com/test, « Ottoman Handwritten (Rika) OCR-Transliteration Dataset », `RiqaTestset.zip` (9,8 Mo), daté du 07.04.2021 (fichier modifié le 2026-02-03). Fournisseur : société de service d'OCR ottoman.
- **Contenu** : 85 pages, 1 575 lignes, écriture rik'a. D'après la documentation de RikaOCR, ce sont 1 575 images de lignes avec leur texte, et les 85 unités sont des documents.
- **Vérité terrain** : écriture arabe et translittération latine. La page ne dit ni qui l'a faite, ni comment (saisie, relecture, assistance d'un modèle).
- **Licence** : aucune licence. Seule mention : les jeux sont « présentés à des fins de recherche et académiques ». La citation demandée pour ce jeu porte le titre du jeu imprimé (probable inversion sur la page).
- **Format** : images de lignes déjà découpées, sans ligne de base. **Conventions** : NFC d'après RikaOCR, le reste est inconnu.
- **Recouvrement** : provenance des documents non indiquée, donc recouvrement avec MAKHZAN invérifiable. Il est faible a priori : les 30 manuscrits ottomans de MAKHZAN sont tous des œuvres titrées, alors que RikaOCR décrit les 85 unités comme des documents. Aucun risque avec le modèle de départ, qui est un modèle d'imprimé.
- **Remarques** : l'écriture rik'a est absente de l'entraînement du projet (100 % naskh). RikaOCR s'en sert comme données d'entraînement.
- **Statut** : le plus proche des critères au niveau de la ligne. Mail envoyé le 2026-09-28 à bilgi@osmanlica.com (licence, droit de publier des scores, origine de la vérité terrain, provenance des documents, citation) ; en attente de réponse. Décision 41.
- **Complément (2026-10-20)** : aucune réponse d'Osmanlica.com au 2026-10-20 (mail du 2026-09-28). F11 est clos sans jeu externe (ROADMAP, ticket F11). Licence et origine de la vérité terrain restent inconnues : le jeu n'est pas utilisé. Une réponse tardive ne rouvrirait pas F11 ; elle alimenterait F15, avec un pré-enregistrement committé avant toute utilisation, et aucune donnée ne serait utilisée sans réponse écrite.
- **Complément (2026-10-29)** : réponse écrite d'Osmanlica.com le 2026-10-23 (İshak, qui travaille avec le professeur Atakan Kurt), à la relance du 2026-10-20 : RiqaTestset est utilisable pour un usage académique ; ils demandent de citer leurs publications. Le 2026-10-29, nouvelle question envoyée : qui a transcrit, avec quelles conventions, et s'il y a eu une relecture ; en attente de réponse. L'origine de la vérité terrain et la provenance des documents restent donc inconnues. Le jeu n'est ni téléchargé ni ouvert. F11 reste clos ; usage prévu en F15 (décision 46).
- **Autres jeux du même fournisseur**, non retenus : deux jeux imprimés naskh (21 pages, 376 lignes ; 21 pages, 436 lignes) ; un jeu de translittération (103 pages, 2 314 lignes, sans description des images).

### 3.4 CHURRO, sous-ensemble ottoman : mémoires d'Osman Ağa de Timişoara

- **Source** : CHURRO-DS (Semnani, Zhang, He, Tekgürler, Lam, EMNLP 2025, arXiv 2509.19768), Hugging Face `stanford-oval/churro-dataset` ; extrait ottoman republié par `OttomanNLP/CHURRO-Ottoman-Turkish-Subset`.
- **Contenu** : manuscrit des mémoires d'Osman Ağa (achevé en 1724, British Library, Or. 3213). L'article annonce 243 images (annexe E) ; la copie OttomanNLP en contient 236, plus une page du jeu Muharaf, en persan, à exclure. Environ 700 caractères par page d'après un échantillon.
- **Vérité terrain** : écriture arabe. D'après l'article (annexe E et références), c'est le texte de l'édition de Richard F. Kreutel, *Die Autobiographie des Dolmetschers Osman Aga aus Temeschwar* (E. J. W. Gibb Memorial Trust, Cambridge, 1980), aligné page par page sur les images par les auteurs de CHURRO. Ce n'est donc pas une transcription faite directement sur les images pour l'HTR : sa fidélité à la page (orthographe du manuscrit, corrections ou normalisations de l'éditeur, limites de page) est à confirmer.
- **Licence** : les sources se contredisent. La fiche du jeu sur Hugging Face le réserve à la recherche (« use is permitted for research purposes only », en raison des licences des jeux qu'il agrège). L'article, section *Ethical Considerations*, annonce CHURRO-DS sous CC BY-SA 4.0 (« released under the Creative Commons Attribution Share Alike 4.0 license »). L'annexe E donne pour le jeu d'Osman Ağa : « permission granted for research use ». La copie OttomanNLP affiche CC BY 4.0, mais c'est un tiers qui a changé l'étiquette : on ne peut pas s'y fier.
- **Format** : image de page et texte de la page **en un seul paragraphe**, sans correspondance ligne par ligne ni ligne de base.
- **Conventions** (échantillon) : ک/ك et ی/ي mêlés, hamza (ؤ), chiffres arabes.
- **Recouvrement** : aucun avec MAKHZAN (cote, bibliothèque et titre vérifiés dans les métadonnées de MAKHZAN 2026.1.2 : ses deux seuls documents de la British Library sont en persan et en arabe). Aucun avec le modèle de départ.
- **Limites** : un seul manuscrit d'une seule main, donc pas d'intervalle de confiance par manuscrit ; alignement texte-lignes à faire, ou CER par page qui inclurait les erreurs de segmentation (contraire à la décision 31).
- **Statut** : mail envoyé le 2026-09-28 à Merve Tekgürler, Sina J. Semnani en copie (licence du sous-ensemble ottoman, compte tenu des sources contradictoires ; existence d'une transcription alignée par ligne ; fidélité à la page de la transcription issue de l'édition de 1980) ; en attente de réponse. Décision 41.
- **Complément (2026-10-20)** : aucune réponse des auteurs de CHURRO au 2026-10-20 (mail du 2026-09-28). F11 est clos sans jeu externe (ROADMAP, ticket F11). Licence du sous-ensemble ottoman et fidélité de la vérité terrain à la page restent inconnues : le jeu n'est pas utilisé. Une réponse tardive ne rouvrirait pas F11 ; elle alimenterait F15, avec un pré-enregistrement committé avant toute utilisation, et aucune donnée ne serait utilisée sans réponse écrite.

### 3.5 RikaOCR

- **Source** : GitHub `umute642-boop/RikaOCR` ; Zenodo 22151212 (v0.10.3, 7,9 Go). Code sous Apache 2.0.
- **Contenu** : modèle kraken rik'a et translittération par ByT5 ; entraîné sur le jeu d'Osmanlica.com (3.3) et testé sur des documents d'archives BOA (9 documents, 132 lignes).
- **Raison de l'exclusion** : la licence des données propres au projet (images BOA, transcriptions) est « en attente de décision » (`LICENSE-DATA`) ; les images BOA ne sont pas distribuées ; 132 lignes seulement.

### 3.6 OtaHTR-search (Enes Yılandiloğlu, Université d'Helsinki)

- **Source** : GitHub `Koras0ff/OtaHTR-search`, licence CC0.
- **Contenu** : interface de recherche par mots-clés dans deux copies du *Divân* de Bâkî (BULAC, MS TURC 52, 197 pages ; Michigan, MS 363, 288 pages), avec régions, lignes et polygones.
- **Raison de l'exclusion** : le texte des lignes est une sortie de reconnaissance automatique, pas une vérité terrain (extraits sans sens, par exemple « باندن دوشتی دلاطش نشونو كچ »).

### 3.7 OpenITI `arabic_ms_data`

- **Source** : GitHub `OpenITI/arabic_ms_data`, sans licence. Données manuscrites d'OpenITI antérieures à MAKHZAN ; source ottomane déclarée du modèle Party (Zenodo 20642057), avec les données imprimées d'OpenITI.
- **Contenu ottoman** : une seule œuvre, une risāle d'Altıparmak (Pertevniyal 981), 10 pages ALTO avec 17 à 19 lignes de base chacune.
- **Raison de l'exclusion** : aucune transcription (texte vide sur les 10 pages : segmentation seule) ; pas de licence.

### 3.8 HTR-United

- **Source** : catalogue `HTR-United/htr-united` (138 jeux).
- **Constat** : aucun jeu ottoman. Jeux en écriture arabe : RASAM (arabe maghrébin, 300 pages, 7 540 lignes, Apache 2.0) et TariMa (arabe maghrébin, 2 673 lignes, CC BY 4.0), réservés à l'entraînement de F15 ; TranscriboQuest (arabe, 153 lignes) ; IRHAS (aljamiado, 10 825 lignes).

### 3.9 Autres sources consultées

| Source | Nature | Raison de l'exclusion |
|--------|--------|-----------------------|
| `mbilir/Osmanlica_Nufus_Defteri` (Hugging Face, CC BY 4.0) | Registre de population BOA, NFS.d 1237, 8 images | Texte par page, mêlé d'équivalents en turc moderne ; trop petit |
| `OttomanNLP/OsmanlicaEkmekveNisastaKitabi` (Hugging Face, CC BY 4.0) | Livre imprimé de 1915, 16 images | Imprimé |
| `OttomanNLP/OpenITI-MAKHZAN-Ottoman-Lines` (Hugging Face) | Lignes de MAKHZAN republiées | Même source que l'entraînement |
| OttomanPages (Osmanlica.com, Zenodo 10.5281/zenodo.22756788) | Segmentation de pages en zones | Pas de texte |
| Jerusalem Marriage Dataset (Zenodo 22693605) ; registres de Satuchin, 1831-1845 (Zenodo 19005184) | Bases de données transcrites | Pas de vérité terrain HTR |
| LATOC (Zenodo 19445113) ; Osmanlica-Bench (Zenodo 21781870) | Corpus de translittération | Texte seul |
| Modèles publics Transkribus (« Ottoman Fatwa Manuscripts », `OttomanTurkish_Print_1`) | Modèles | Vérité terrain non publique |
| Ottoman Text Recognition Network (Université de Vienne) | Réseau de chercheurs | Pas de jeu public ; accès sur demande |
| eScriptorium | Plateforme | Pas de catalogue public ; les jeux exportés passent par Zenodo et HTR-United, déjà examinés |
| `Kutlu24/ottoman-rag` | Système RAG | Pas de données, pas de licence |

## 4. Sources

Consultées le 2026-09-28.

- MAKHZAN : https://doi.org/10.5281/zenodo.19861912 ; https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.465
- Akis : https://github.com/verimsu/Akis-Ottoman-Dataset ; article : https://doi.org/10.1007/978-3-031-70442-0_26
- Osmanlica.com : https://osmanlica.com/test
- CHURRO : https://arxiv.org/abs/2509.19768 (texte HTML de la v1 : section *Ethical Considerations* ; annexe E, « The Osman Agha dataset » ; référence « Osman agha dataset ») ; https://huggingface.co/datasets/stanford-oval/churro-dataset ; https://huggingface.co/datasets/OttomanNLP/CHURRO-Ottoman-Turkish-Subset
- RikaOCR : https://github.com/umute642-boop/RikaOCR ; https://zenodo.org/records/22151212
- OtaHTR-search : https://github.com/Koras0ff/OtaHTR-search
- OpenITI `arabic_ms_data` : https://github.com/OpenITI/arabic_ms_data ; modèle Party : https://zenodo.org/records/20642057
- HTR-United : https://htr-united.github.io/ ; catalogue : https://github.com/HTR-United/htr-united
- Hugging Face : https://huggingface.co/datasets/asparius/ottoman-ocr-8k ; https://huggingface.co/datasets/mbilir/Osmanlica_Nufus_Defteri ; https://huggingface.co/datasets/OttomanNLP/OsmanlicaEkmekveNisastaKitabi
- OttomanPages : https://github.com/Osmanlica-com/OttomanPages
- ottoman-rag : https://github.com/Kutlu24/ottoman-rag
- Ottoman Text Recognition Network : https://otrn.univie.ac.at/
- Recherches Zenodo (API) : « ottoman » avec htr, ocr, ground truth, transcription, kraken, escriptorium ; « osmanlıca » ; « Ottoman Turkish » avec manuscript, handwritten, dataset ; ottoman avec alto ou page xml ; rika, riqa.
