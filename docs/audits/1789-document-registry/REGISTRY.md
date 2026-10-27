# Schéma du registre

Une ligne = une entrée Persée `griev`, sans suppression des listes ni fusion de deux notices. `id = ap1789-registry-p1:<identifiant Persée>` : l’identité ne change pas lors d’une correction de frontière. Les identifiants Persée sont bibliographiques ; les identifiants internes et `source_witness_id` sont techniques.

`metadata` conserve titre, genre METS/DC, volume, pages, citation, URL, ordre du catalogue, ancêtres METS, date d’édition, champs DC bruts, droits, identifiant OAI, datestamp et empreintes des témoins. **1879 désigne l’édition**, pas la rédaction. La date historique reste nulle tant qu’elle n’est pas extraite et vérifiée. Une localité ou un ordre contenus dans un titre ne deviennent pas silencieusement des métadonnées historiques certifiées.

`document_kind` est une hypothèse : `cahier_autonome_probable`, `document_associe`, `proces_verbal`, `extrait`, `liste`, `autre_document`, `notice_absence`, éventuellement `incertain`. Le type `griev` ne discrimine pas ces genres. La règle sur les groupes professionnels est conservatrice et doit être réexaminée : un cahier de corporation peut aussi constituer une unité autonome. Un PV peut contenir un vrai cahier. Le champ `document_kind_reference`, lorsqu’il existe, conserve le diagnostic de lecture distinct.

`alignment_status` : `fort`, `probable`, `ambigu`, `non_retrouve`, `hors_perimetre`. Ni le score ni la marge ne sont des probabilités. `alignment_verification` distingue la proposition et le contrôle Codex. Les erreurs observées ne sont pas corrigées en choisissant silencieusement une alternative.

`candidates` conserve jusqu’à cinq possibilités : XPath de division et d’ancre interne, positions, titres/contextes OCR, page et sa méthode, couvertures lexicales, conflit d’ordre, soutien V2 et score. La première proposition n’est pas nécessairement la bonne. `catalogue_neighbours` désigne les voisins du catalogue, sans les confondre avec les voisins physiques XML.

## Plages et frontières

`boundaries.proposal` est la prédiction d’origine avec `[start,end)`, divisions, pages et alertes. `boundaries.status` : `verifiees`, `proposees`, `ambigues`, `non_etablies`. `verification` indique l’origine du contrôle ; une frontière « vérifiée » signifie ici **extrémités examinées par Codex dans le TEI**, pas certification historique ni contrôle d’OCR.

Les 26 références héritées et 52 nouvelles références conformes sont dans `verified_reference`. Lorsqu’une référence héritée corrige une proposition, `active_reference_range` l’explicite ; la proposition n’est pas écrasée. Les 15 erreurs nouvelles restent sans plage corrigée certifiée. `source_slice_sha256` contrôle la plage **proposée**, même lorsqu’elle est incorrecte. Cette empreinte ne certifie pas son attribution documentaire.

Les offsets sont des points de code Unicode du flux décodé `itertext` reconstruit par le helper du pilote, **pas des octets XML**, ni des indices dans un texte dont les espaces ont été normalisés. La source, sa révision et son SHA-256 font partie du contrat. Pour retrouver le texte exact : charger le même objet `Source`, puis `source.text[start:end]`. Ne pas appliquer ces offsets à une autre version.

`locator` donne les éléments textuels voisins des extrémités ; la borne peut inclure de l’espace entre éléments. `page_references` conserve les `pb`, leurs identifiants et numéros disponibles ; `source.scan_url` donne la numérisation Stanford. Ne pas confondre le suffixe de l’image et la page imprimée. `structure_proposals` pointe les titres, notes XML, rubriques et indices de signatures/certifications sans réécrire leur texte. Les notes imprimées absorbées dans un `p` ne sont pas toutes reconnues.

## Compléments et compatibilité

- `stanford-comparison.jsonl.gz` : les 1 954 prédictions V2, avec correspondance d’ancre et inclusion dans une plage proposées séparément.
- `stanford-complement.jsonl` : 92 propositions autonomes/associées sans équivalence d’ancre. Inclusion dans une plage ne vaut pas identité.
- `stanford-uncertain.jsonl` : 55 hypothèses incertaines V2, y compris les pièces non admises.
- `id-crosswalk.jsonl` : liens vers les identifiants du pilote et des ancres V2.
- `previous-document-crosswalk.jsonl` : conservation explicite des 200 anciens identifiants documentaires, y compris ceux sans correspondance. `overlap_not_certified_identity` ne doit jamais servir de remplacement automatique.

Le modèle futur reste `Corpus → Document (cahier ou pièce associée) → Article/passage → Segment`. Les articles et segments **ne sont pas produits**. Leur futur identifiant pourra associer l’ID parent, l’empreinte source, la version du segmenteur et les bornes. Conserver ordre, ancre d’affichage et voisins à cette future étape. Une correction doit ajouter une décision et une correspondance d’anciennes bornes, pas modifier le texte historique ni supprimer les références précédentes.
