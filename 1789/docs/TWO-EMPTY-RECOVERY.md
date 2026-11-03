# Deux cahiers retrouvés — collection de référence stabilisée

La collection active est **`data/documents/reference-documents-2-7cbcaea79991`**. Elle remplace comme référence la génération `reference-documents-1-b8b8b20c2f76`, intégralement conservée. G6 et les annotations historiques restent inchangées. Aucun autre dossier documentaire n’a été repris.

## Diagnostic commun

Les textes n’étaient pas absents de Stanford : les bonnes divisions avaient déjà été trouvées. L’ancienne fonction `boundary` de `archives/1789-persee-stanford-alignment/alignment.py` considérait tout paragraphe `CAHIER` situé après la position de début de division comme un nouveau cahier, lorsque le paragraphe suivant contenait un indice d’identité.

Or la position de début de division précède de **25 caractères blancs** son premier paragraphe `CAHIER`. Le détecteur a donc traité **le propre titre initial du document** comme une frontière suivante et arrêté l’extraction avant tout contenu. Les deux alertes anciennes étaient `next_literal_internal_cahier_title` et `end_page_mismatch_requires_review`.

Cette mission corrige uniquement les deux références examinées. Elle ne modifie pas ce détecteur historique et ne le relance pas. La correction est décrite dans `extraction/two-empty-document-repairs.json`, avec positions, XPath, empreintes, titres, clôtures et voisins.

## Clergé de la province du Quercy

Notice `arcpa_0000-0000_1879_num_5_1_2837`, tome V, **483–484**.

Le texte est dans `/TEI.2/text/body/div1/div2[12]/div3[2]`. Ses deux premiers paragraphes portent « CAHIER » puis « Des doléances et observations du clergé, abbés chapitres et prieurs […] du Quercy ». Le contenu, les signatures des évêques de Cahors et Montauban, puis la collation et la signature finale du greffier confirment l’identité et la clôture.

La division précédente contient le procès-verbal et les comparants des trois ordres. La suivante commence **un autre cahier**, celui des curés de paroisse du Quercy : il n’a pas été absorbé. La mention du greffier du tiers-état dans la collation est conservée telle qu’elle figure dans Stanford ; elle n’a pas été corrigée ou utilisée pour réattribuer le document.

| Élément | Résultat |
|---|---|
| Ancienne plage Unicode | `[4343092, 4343117[` — 25 blancs |
| Nouvelle plage Unicode | **`[4343092, 4360210[`** |
| Texte intégral | **17 118 caractères** |
| Passages techniques | **6** |
| Pagination Stanford | 483–484, conforme à Persée |

## Tiers état de Saint-Pierre-le-Moutier

Notice `arcpa_0000-0000_1879_num_5_1_2877`, tome V, **635–643**.

Le cahier principal est dans `/TEI.2/text/body/div1/div2[22]/div3[2]`. Le titre identifie la chambre du tiers-état du bailliage royal du Nivernais à Saint-Pierre-le-Moutier. Le texte se termine par l’arrêté du **22 mars 1789** et une longue liste de signatures. Le cahier de noblesse qui le précède reste distinct.

Le dossier est conservé avec ses composantes explicites :

| Division Stanford | Rôle conservé | Pages | Plage source |
|---|---|---|---|
| `div3[2]` | Cahier principal, avec clôture et signatures | 635–642 | `[5683756, 5750736[` |
| `div3[3]` | Pétition particulière de Château-Chinon en Morvan, pièce associée | 642–643 | `[5750757, 5756860[` |
| `div3[4]` | Pétitions de Pouilly-sur-Loire, explicitement jointes au cahier général | 643 | `[5756881, 5760887[` |

Le titre de Pouilly précise « pour être jointes au cahier général du bailliage royal de Saint-Pierre-le-Moutier et ressort ». La succession des pièces dans le même dossier territorial Stanford et l’intervalle Persée 635–643 étayent ce regroupement. **Château-Chinon reste identifié comme une pièce associée par le contexte documentaire : cela ne prouve pas une rédaction commune avec le cahier principal.** Cette distinction est conservée dans `document_components`, ses champs de relation et les références de composantes des passages. Les pièces ne deviennent ni de nouveaux cahiers ni des articles du corps principal.

Le cahier de **Cusset**, `div3[5]`, commence ensuite, avec une nouvelle ouverture documentaire, à la position 5760908. Il est exclu. Sa frontière et son texte n’ont pas été modifiés. Les notes éditoriales, y compris celles imprimées sur la page partagée et conservées par Stanford dans le paragraphe d’ouverture, restent dans le texte source et sont référencées séparément comme notes.

| Élément | Résultat |
|---|---|
| Ancienne plage Unicode | `[5683756, 5683781[` — 25 blancs |
| Nouveau dossier, avec composantes distinguées | **`[5683756, 5760887[`** |
| Texte intégral | **77 131 caractères** |
| Passages techniques | **27** |
| Pagination Stanford du dossier | 635–643, conforme à Persée |

Les espaces entre les trois divisions sont conservés. Le découpage technique peut traverser une jonction de composantes ; leurs références restent disponibles. Le regroupement documentaire ne prétend pas transformer ces pièces en une seule revendication.

## Bilan final

| Indicateur | Avant | Après |
|---|---:|---:|
| Notices | 1 305 | 1 305 |
| Documents conservés | 1 267 | 1 267 |
| Cahiers probables avec texte substantiel | 1 222 | **1 224** |
| Plages uniquement blanches | 2 | **0** |
| Passages techniques, tous documents | 11 358 | **11 391** |
| Dont passages dans les cahiers probables | 10 717 | **10 750** |
| Caractères sources dans les parents | 30 656 665 | **30 750 864** |
| Couverture des caractères des parents par les passages, hors répétitions | hors 50 blancs explicitement exclus | **100 %** |
| Passages dépassant 800 tokens | 0 | **0** |
| Erreurs d’intégrité | 0 | **0** |
| Nouveaux chevauchements documentaires | — | **0** |

La moyenne reste de 591,1 tokens ; le maximum est 800. Les règles de découpage, la configuration, le tokenizer et l’empreinte des règles sont strictement identiques. Les nouveaux passages portent la même version technique, avec de nouveaux identifiants dérivés de leurs nouvelles étendues sources.

**1 265 documents et 11 358 passages précédents sont identiques, champ par champ**, avec les mêmes identifiants. Les métadonnées Persée et le tirage visuel précédent sont identiques octet par octet. `extent-crosswalk.jsonl.gz` relie les deux anciennes étendues vides aux nouvelles, sans changer les identifiants documentaires du registre.

Les deux périmètres ont été **examinés dans le XML par Codex, pas validés humainement**. Leur ancien état et les propositions initiales restent traçables. Aucune décision humaine, même ancienne ou annulée, ne concerne ces deux documents ; le script refuserait leur remplacement si un tel historique existait. Les **45 frontières humaines**, **605 articles humains**, les **56 événements de frontières** et **697 événements d’articles** restent préservés. Les journaux originaux et leurs instantanés sont identiques octet par octet. Les anciennes annotations G6 ne sont pas transférées aux textes récupérés : elles restent explicitement attachées aux anciennes étendues.

Les 38 notices sans texte, les autres alertes documentaires et les deux chevauchements hérités ne sont pas réexaminés. Le rattachement contextuel de Château-Chinon est documenté sans certification d’auteur. La disparition des deux plages vides ne certifie pas automatiquement toutes les frontières du corpus.

## Accès et reproduction

Redémarrer le serveur existant :

```sh
python3 1789/review.py
```

- [Ouvrir le clergé du Quercy](http://127.0.0.1:1789/passages?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2837).
- [Ouvrir Saint-Pierre-le-Moutier](http://127.0.0.1:1789/passages?document=ap1789-registry-p1%3Aarcpa_0000-0000_1879_num_5_1_2877).

La vue en lecture seule affiche le texte, ses passages surlignés et les rôles des composantes. Aucun nouveau contrôle manuel des revendications n’est demandé. L’ancien outil documentaire continue de montrer l’état historique G6 ; les réparations sont portées par la nouvelle collection de référence, sans réécriture de G6.

```sh
# Contrôle complet seul :
python3 1789/extraction/prepare_documents.py --verify-only 1789/data/documents/reference-documents-2-7cbcaea79991

# Constructeur de cette transition, sans segmentation historique :
python3 1789/extraction/repair_reference_documents.py
```

Le constructeur refuse d’écraser sa sortie immuable existante. Pour contrôler la collection livrée, utiliser `--verify-only`. Les entrées, décisions privées figées, empreintes, corrections documentées et générations précédentes restent conservées. **Ne pas relancer le constructeur initial G6 → référence 1 pour remplacer cette collection corrigée.**

Les 92 tests Python passent. Les contrôles après relecture des fichiers produits vérifient le texte exact, les positions, la couverture, les tailles, les références, l’unicité et la stabilité des identifiants. Trois documents non modifiés des tomes I, IV et VI reproduisent également leurs passages à l’identique avec la représentation réutilisée. Les essais navigateur couvrent les douze fenêtres antérieures et les deux documents récupérés, sans POST ni écriture humaine.

La préparation de la collection est **terminée sur ce périmètre**, avec les incertitudes résiduelles explicites. Aucun embedding, index, accès PostgreSQL, site public, OCR ou segmenteur historique n’a été utilisé.

[Résultats structurés des contrôles](two-empty-repairs-checks.json).
