# Comparaison des méthodes

Notes Codex exploratoires et non indépendantes. Moyennes sur 30 requêtes. Notes moyennes sur 0–3, positions non retournées = 0. nDCG sur le pool jugé (gains 2^note−1), pas un rappel exhaustif. Part forte : note 3 parmi résultats retournés. Hors sujet : note 0 ; la note 1 reste superficielle. nDCG gradué sur 26 requêtes historiques / 30 mixtes ; variante utile sur 21 historiques / 25 mixtes. Les idéaux nuls sont exclus des moyennes et signalés, pas convertis en succès.

## Population historical

| Méthode | Note@5 | Note@10 | nDCG@10 | Forte | Hors sujet | Résultats | Historiques utiles / requête |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | 1.373 | 1.313 | 0.555 | 19.1% | 23.0% | 283 | 4.07 |
| vector_A | 1.600 | 1.450 | 0.696 | 24.3% | 25.3% | 300 | 4.60 |
| vector_B | 1.573 | 1.440 | 0.687 | 22.7% | 25.3% | 300 | 4.67 |
| hybrid_A | 1.553 | 1.453 | 0.660 | 24.3% | 26.7% | 300 | 4.77 |
| hybrid_B | 1.560 | 1.467 | 0.664 | 24.0% | 26.3% | 300 | 4.90 |

| Catégorie | Méthode | Note@10 | nDCG@10 utile (notes≥2) | Requêtes avec un utile connu |
|---|---|---:|---:|---:|
| contemporaine | lexical | 1.733 | 0.456 | 12 |
| contemporaine | vector_A | 1.992 | 0.681 | 12 |
| contemporaine | vector_B | 1.967 | 0.651 | 12 |
| contemporaine | hybrid_A | 2.000 | 0.655 | 12 |
| contemporaine | hybrid_B | 2.000 | 0.657 | 12 |
| historique | lexical | 2.100 | 0.733 | 6 |
| historique | vector_A | 1.983 | 0.717 | 6 |
| historique | vector_B | 1.983 | 0.736 | 6 |
| historique | hybrid_A | 2.183 | 0.807 | 6 |
| historique | hybrid_B | 2.217 | 0.830 | 6 |
| ambigue | lexical | 0.983 | 0.457 | 3 |
| ambigue | vector_A | 1.183 | 0.714 | 3 |
| ambigue | vector_B | 1.217 | 0.795 | 3 |
| ambigue | hybrid_A | 1.050 | 0.529 | 3 |
| ambigue | hybrid_B | 1.083 | 0.547 | 3 |
| contre_exemple | lexical | 0.017 | — | 0 |
| contre_exemple | vector_A | 0.100 | — | 0 |
| contre_exemple | vector_B | 0.067 | — | 0 |
| contre_exemple | hybrid_A | 0.033 | — | 0 |
| contre_exemple | hybrid_B | 0.033 | — | 0 |

## Population mixed

| Méthode | Note@5 | Note@10 | nDCG@10 | Forte | Hors sujet | Résultats | Historiques utiles / requête |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | 1.360 | 1.280 | 0.448 | 18.0% | 25.8% | 295 | 2.57 |
| vector_A | 1.660 | 1.540 | 0.633 | 25.0% | 15.3% | 300 | 2.07 |
| vector_B | 1.527 | 1.467 | 0.597 | 21.7% | 14.0% | 300 | 1.00 |
| hybrid_A | 1.667 | 1.577 | 0.594 | 26.7% | 18.3% | 300 | 3.00 |
| hybrid_B | 1.667 | 1.527 | 0.588 | 24.3% | 18.0% | 300 | 2.30 |

| Catégorie | Méthode | Note@10 | nDCG@10 utile (notes≥2) | Requêtes avec un utile connu |
|---|---|---:|---:|---:|
| contemporaine | lexical | 1.608 | 0.406 | 12 |
| contemporaine | vector_A | 1.917 | 0.560 | 12 |
| contemporaine | vector_B | 1.733 | 0.420 | 12 |
| contemporaine | hybrid_A | 2.017 | 0.589 | 12 |
| contemporaine | hybrid_B | 1.908 | 0.544 | 12 |
| historique | lexical | 1.817 | 0.631 | 6 |
| historique | vector_A | 1.767 | 0.583 | 6 |
| historique | vector_B | 1.583 | 0.484 | 6 |
| historique | hybrid_A | 2.050 | 0.757 | 6 |
| historique | hybrid_B | 1.917 | 0.705 | 6 |
| ambigue | lexical | 1.100 | 0.358 | 5 |
| ambigue | vector_A | 1.533 | 0.454 | 5 |
| ambigue | vector_B | 1.700 | 0.555 | 5 |
| ambigue | hybrid_A | 1.417 | 0.465 | 5 |
| ambigue | hybrid_B | 1.483 | 0.544 | 5 |
| contre_exemple | lexical | 0.267 | 0.219 | 2 |
| contre_exemple | vector_A | 0.567 | 0.883 | 2 |
| contre_exemple | vector_B | 0.583 | 0.883 | 2 |
| contre_exemple | hybrid_A | 0.383 | 0.440 | 2 |
| contre_exemple | hybrid_B | 0.417 | 0.440 | 2 |
