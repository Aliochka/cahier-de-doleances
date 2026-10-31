# Formats et provenance

La source documentaire reste `1789-document-registry/data/registry.jsonl.gz`. Les six XML sont lus avec les helpers existants et leurs empreintes de la révision Stanford `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Aucun fichier Persée intégral n’est téléchargé. Les métadonnées Persée restent décrites comme telles, distinctes des textes Stanford et de leurs conditions de réutilisation.

## Fichiers locaux calculés

| Fichier sous `data/` | Contenu |
| --- | --- |
| `selection.json` | 30 IDs du registre, motifs, références antérieures et provenance du choix |
| `parents.jsonl.gz` | Textes intégraux des périmètres retenus, blocs, sections, annotations, empreintes et métadonnées |
| `units-A.jsonl.gz` | Articles dont les frontières reprennent une référence Codex examinée et encore utilisable |
| `units-B.jsonl.gz` | Articles proposés, références anciennes demandant réexamen et sections proposées |
| `units-C.jsonl.gz` | Compléments techniques non assimilés à des articles historiques |
| `automatic-proposals.jsonl.gz` | Résultat brut du segmenteur V2, avant rapprochement des références d’articles |
| `crosswalk.jsonl` | Ancien ID d’unité → nouvel ID, tranche/texte identiques, statut explicite |
| `withheld.json` | Dossiers non exportés : incertitude, blocage, source ancienne ou périmètre non établi |
| `source-manifest.json` | Sources et codes réutilisés, empreintes et révision |
| `extraction-manifest.json` | Empreintes et tailles des exports locaux ; gzip à date nulle, reproductible |
| `quality.json` | Résultats des contrôles matériels, volumes et statuts |
| `review-summary.json` | Bilan du vrai journal humain ; les essais temporaires n’y figurent pas |
| `small-examples.json` | Trois préfixes de texte exacts pour illustrer A/B/C, explicitement incomplets |
| `browser-checks.json` | Résultats des tests navigateur sur un journal synthétique isolé |

Les gros exports et le journal personnel restent ignorés. Les fichiers nécessaires aux expériences antérieures retirés de Git sont toujours nécessaires localement ; voir `../LOCAL_DATA.md`. Un clone seul ne suffit pas à reconstruire les unités si ces références locales manquent.

## Identité et positions

Le parent garde l’ID stable du registre `ap1789-registry-p1:…` et l’identifiant Persée. Un `extent_id` distinct identifie sa version de texte à partir du parent, de l’empreinte XML et des deux positions. Un changement de limites produit une nouvelle version, sans modifier l’ID documentaire.

Les unités `ap1789-unit-1:…` sont déterministes pour la version de méthode, le type, la version du périmètre et leurs plages. Aucun ID antérieur n’est réutilisé avec un contenu différent. Les anciens parents recouvrant le nouveau sont conservés comme relations `exact` ou `overlapping_extent_not_equivalent` ; les anciens articles ne sont reliés comme équivalents que si leur texte et leurs positions correspondent.

Les positions sont des **points de code Unicode dans le texte décodé `itertext()` du volume**, plages semi-ouvertes `[start,end)`. Ce ne sont ni des octets XML ni des indices UTF-16 JavaScript. L’interface enregistre des IDs de blocs ; le serveur calcule ces positions sans demander une conversion à l’utilisateur. Les IDs de blocs `vN-bXXXXXX` réutilisent la convention de l’audit précédent, avec les sauts de page dans l’index ; un saut de page ne peut pas devenir une limite sélectionnée.

Chaque unité contient `parent_id`, `parent_extent_id`, `type`, `status`, `historical_number`, `label_exact`, `text`, `text_spans`, `parent_text_spans`, `parent_start/end`, `xml_blocks`, `pages`, `source`, `section_id`, `order`, `previous_unit_id`, `next_unit_id` et `extraction_version`. Le texte est la concaténation exacte de ses tranches source, **sans séparateur ajouté**. Une note exclue de la parole d’un article reste dans le parent et dans les compléments C.

Les voisins suivent l’ordre technique des unités extraites, tous types confondus. `neighbour_order_status` précise qu’il ne s’agit pas d’une succession historique exhaustivement certifiée. Les sections du parent conservent leurs intitulés et une portée proposée ; une section peut regrouper plusieurs articles. Les dix unités de type `section` représentent uniquement des plages non déjà occupées par des articles.

`search_eligible` est un indicateur conservateur pour une future expérimentation, pas une certification : les articles A/B sont proposés, les sections ne sont pas autorisées automatiquement, les passages C mêlés au paratexte sont exclus. **Ne pas indexer indistinctement tous les compléments C.** Les blancs conservés assurent la fidélité et la couverture sans constituer du contenu de recherche utile.

## Deux niveaux de vérification

Le parent conserve `boundary_status`, `boundary_origin` et l’éventuel événement humain. Les unités ont leur propre vérification A/B/C. Même après validation humaine du parent, une unité B reste B. Le champ `human_validated` des unités reste faux : cette version de l’outil vérifie les parents, pas les articles.

La priorité des références est : décision humaine compatible (y compris incertitude/blocage), référence Codex documentaire récente établie, référence vérifiée du registre, parent vérifié du pilote pour le lot initial, puis proposition automatique. Les propositions originelles restent enregistrées. Les références récentes difficiles/non établies ne sont pas transformées en bornes certifiées ; elles restent accessibles dans les audits d’origine.

Les cinq anciennes unités de ce lot signalées pour réexamen par les diagnostics V2 restent B. Les autres A sont des reprises explicites de contrôles TEI anciens, pas de nouvelles vérifications fac-similé ou validations humaines. Le français historique et l’OCR restent inchangés.
