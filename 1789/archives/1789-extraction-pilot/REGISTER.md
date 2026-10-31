# Registre des 30 cahiers

Généré par `render_reports.py`. Sélection raisonnée, non représentative. Les sept cas hérités sont signalés ; les 23 autres sont les ajouts du pilote. Les statuts de frontières résultent d’une revue XML par Codex, pas d’une expertise humaine indépendante.

Les XPath ci-dessous sont relatifs à `/TEI.2/text/body/div1`. Les références complètes, offsets, sections, dates, titres source et incertitudes sont dans [register.json](data/register.json) et [decisions.json](decisions.json). Une page `?` indique un libellé imprimé absent du `pb`, jamais remplacé par le numéro d’image.

| Cahier et texte intégral | Vol. | Ordre explicite | Sélection | Pages TEI | Frontière automatique | Unités A / B |
|---|---:|---|---|---|---|---:|
| [Clergé d’Agenois](data/parents/agen-clerge.txt) | 1 | clergé | hérité | ?–679 | conforme | 9 / 61 |
| [Noblesse d’Agenois](data/parents/agen-noblesse.txt) | 1 | noblesse | ajout | 679–686 | conforme | 3 / 56 |
| [Tiers état d’Agenois](data/parents/agen-tiers.txt) | 1 | tiers état | ajout | 686–691 | conforme | 0 / 0 |
| [Clergé d’Alençon](data/parents/alencon-clerge.txt) | 1 | clergé | ajout | ?–710 | conforme | 5 / 81 |
| [Noblesse d’Alençon](data/parents/alencon-noblesse.txt) | 1 | noblesse | ajout | 710–716 | conforme | 2 / 10 |
| [Noblesse d’Angoumois](data/parents/angoumois-noblesse.txt) | 2 | noblesse | hérité | 3–7 | conforme | 5 / 51 |
| [Clergé d’Anjou](data/parents/anjou-clerge.txt) | 2 | clergé | ajout | 30–32 | conforme | 18 / 62 |
| [Clergé d’Annonay](data/parents/annonay-clerge.txt) | 2 | clergé | ajout | 46–47 | conforme | 13 / 18 |
| [Noblesse du Beaujolais](data/parents/beaujolais-noblesse.txt) | 2 | noblesse | ajout | 281–282 | conforme | 15 / 17 |
| [Tiers état de Lawastine](data/parents/lawastine-tiers.txt) | 2 | tiers état | ajout | 192 | conforme | 5 / 0 |
| [Ville de Colmar](data/parents/colmar-ville.txt) | 3 | non attribué | hérité | 12–15 | conforme | 8 / 28 |
| [Communauté de Ribaucourt](data/parents/ribaucourt.txt) | 3 | non attribué | ajout | 194–195 | conforme | 11 / 0 |
| [Habitants de Flines](data/parents/flines.txt) | 3 | non attribué | ajout | 204–205 | conforme | 13 / 0 |
| [Frères mineurs de Carces](data/parents/carces-mineurs.txt) | 3 | clergé | ajout | 273–274 | conforme | 8 / 0 |
| [Montigny en Ostrevent](data/parents/montigny-ostrevent.txt) | 3 | non attribué | ajout | 222–223 | conforme | 11 / 8 |
| [Noblesse de Mirecourt](data/parents/mirecourt-noblesse.txt) | 4 | noblesse | hérité | 1–6 | conforme | 13 / 12 |
| [Tiers état de la sénéchaussée de Guérande](data/parents/guerande-tiers.txt) | 4 | tiers état | hérité | 103–105 | conforme | 8 / 19 |
| [Tiers état de Ferrières en Brie](data/parents/ferrieres.txt) | 4 | tiers état | ajout | 545–546 | conforme | 24 / 1 |
| [Annet-sur-Marne](data/parents/annet-marne.txt) | 4 | non attribué | ajout | 297–298 | conforme | 15 / 0 |
| [Ermenonville / Arnouville](data/parents/ermenonville.txt) | 4 | non attribué | ajout | 316 | conforme | 12 / 0 |
| [Clergé de Mirecourt](data/parents/mirecourt-clerge.txt) | 4 | clergé | ajout | 1 | conforme | 5 / 0 |
| [Habitants de Pierrelez](data/parents/pierrelez-habitants.txt) | 5 | non attribué | hérité | 21 | conforme | 9 / 0 |
| [Tiers état de Périgny-en-Brie](data/parents/perigny-brie.txt) | 5 | tiers état | ajout | 14 | conforme | 15 / 0 |
| [Tiers état du Plessis-Secqueville](data/parents/plessis-secqueville.txt) | 5 | tiers état | ajout | 30–31 | conforme | 9 / 0 |
| [Habitants de Puteaux](data/parents/puteaux.txt) | 5 | non attribué | ajout | 47–48 | conforme | 11 / 0 |
| [Clergé du bailliage de Vie [graphie TEI]](data/parents/vic-clerge.txt) | 6 | clergé | hérité | 16–18 | conforme | 8 / 34 |
| [Noblesse de Toul et pays toulois](data/parents/toul-noblesse.txt) | 6 | noblesse | ajout | 4–8 | conforme | 2 / 32 |
| [Habitants d’Albertas](data/parents/albertas.txt) | 6 | non attribué | ajout | 237 | conforme | 9 / 0 |
| [Habitants de Beaurecueil](data/parents/beaurecueil.txt) | 6 | non attribué | ajout | 262 | corrigée | 3 / 0 |
| [Habitants de Lourmarin](data/parents/lourmarin.txt) | 6 | non attribué | ajout | 320–321 | conforme | 0 / 0 |

## Références, motifs et limites

### agen-clerge

**Clergé d’Agenois**, volume 1 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml), [volume numérisé](https://purl.stanford.edu/jt959wc5586), [fragment XML de contrôle](data/parents/agen-clerge.xml).

Références : `div2[6]/div3[1]`. Plage décodée du volume : `[5119872, 5153454)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:jt959wc5586:64bb7420785d8cb8ea4b`.

Motif : articles multi-paragraphes ; sept initiaux.

Date de présentation : 1789-03-23. Provenance : p157 Fait et arrêté ; p180 approbation le même jour.

Résultat : 69 candidats automatiques avant revue ; 9 A et 61 B après revue. 9 décisions de rôles/plages, hors annotations des unités de référence.

### agen-noblesse

**Noblesse d’Agenois**, volume 1 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml), [volume numérisé](https://purl.stanford.edu/jt959wc5586), [fragment XML de contrôle](data/parents/agen-noblesse.xml).

Références : `div2[6]/div3[2]`. Plage décodée du volume : `[5153475, 5223632)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:jt959wc5586:e3853dbbb35a07b290ab`.

Motif : long ; signatures étendues.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 66 candidats automatiques avant revue ; 3 A et 56 B après revue. 10 décisions de rôles/plages, hors annotations des unités de référence.

### agen-tiers

**Tiers état d’Agenois**, volume 1 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml), [volume numérisé](https://purl.stanford.edu/jt959wc5586), [fragment XML de contrôle](data/parents/agen-tiers.xml).

Références : `div2[6]/div3[3]`. Plage décodée du volume : `[5223653, 5272904)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:jt959wc5586:b111f61f6392ebab8939`.

Motif : long ; en-tête courant OCR dans un paragraphe.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 0 candidats automatiques avant revue ; 0 A et 0 B après revue. 7 décisions de rôles/plages, hors annotations des unités de référence.

### alencon-clerge

**Clergé d’Alençon**, volume 1 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml), [volume numérisé](https://purl.stanford.edu/jt959wc5586), [fragment XML de contrôle](data/parents/alencon-clerge.xml).

Références : `div2[9]/div3[1]`. Plage décodée du volume : `[5411586, 5435510)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:jt959wc5586:c8caba17ed36b64403f1`.

Motif : long ; clôture et collation.

Date de présentation : 1789-03-27. Provenance : p2 Du27 mars 1789.

Résultat : 85 candidats automatiques avant revue ; 5 A et 81 B après revue. 15 décisions de rôles/plages, hors annotations des unités de référence.

### alencon-noblesse

**Noblesse d’Alençon**, volume 1 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml), [volume numérisé](https://purl.stanford.edu/jt959wc5586), [fragment XML de contrôle](data/parents/alencon-noblesse.xml).

Références : `div2[9]/div3[2]`. Plage décodée du volume : `[5435531, 5492248)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:jt959wc5586:bcdc69723b9153e44463`.

Motif : long ; listes de députés.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 12 candidats automatiques avant revue ; 2 A et 10 B après revue. 5 décisions de rôles/plages, hors annotations des unités de référence.

### angoumois-noblesse

**Noblesse d’Angoumois**, volume 2 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml), [volume numérisé](https://purl.stanford.edu/fz023dp4399), [fragment XML de contrôle](data/parents/angoumois-noblesse.xml).

Références : `div2[1]/div3[2]`. Plage décodée du volume : `[16826, 49888)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:fz023dp4399:116d12e81ebea8a7220b`.

Motif : article-charte et sous-listes ; sept initiaux.

Date de présentation : non extraite de manière fiable. Provenance : Titre : les 16, 17, 18, 19 et jours suivants de mars 1789 ; ne pas transformer en date unique..

Résultat : 56 candidats automatiques avant revue ; 5 A et 51 B après revue. 8 décisions de rôles/plages, hors annotations des unités de référence.

### anjou-clerge

**Clergé d’Anjou**, volume 2 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml), [volume numérisé](https://purl.stanford.edu/fz023dp4399), [fragment XML de contrôle](data/parents/anjou-clerge.xml).

Références : `div2[2]/div3[1]`; `div2[2]/div3[2]`; `div2[2]/div3[3]`. Plage décodée du volume : `[212002, 227226)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:fz023dp4399:b1c515d7e3ec55e7f988`.

Motif : trois divisions ; chapitres et reprises de numérotation.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 80 candidats automatiques avant revue ; 18 A et 62 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### annonay-clerge

**Clergé d’Annonay**, volume 2 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml), [volume numérisé](https://purl.stanford.edu/fz023dp4399), [fragment XML de contrôle](data/parents/annonay-clerge.xml).

Références : `div2[3]/div3[1]`. Plage décodée du volume : `[317034, 322650)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:fz023dp4399:b7bcc2acbfad93e812c1`.

Motif : articles ; signatures coupées entre paragraphes.

Date de présentation : 1789-03-26. Provenance : p31 Ainsi arrêté.

Résultat : 31 candidats automatiques avant revue ; 13 A et 18 B après revue. 2 décisions de rôles/plages, hors annotations des unités de référence.

### beaujolais-noblesse

**Noblesse du Beaujolais**, volume 2 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml), [volume numérisé](https://purl.stanford.edu/fz023dp4399), [fragment XML de contrôle](data/parents/beaujolais-noblesse.xml).

Références : `div2[19]/div3[2]`. Plage décodée du volume : `[1938359, 1946016)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:fz023dp4399:3e6a4db201abec55cb3e`.

Motif : articles puis demandes particulières numérotées.

Date de présentation : 1789-03-19. Provenance : head séance du 19 mars.

Résultat : 23 candidats automatiques avant revue ; 15 A et 17 B après revue. 1 décisions de rôles/plages, hors annotations des unités de référence.

### lawastine-tiers

**Tiers état de Lawastine**, volume 2 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml), [volume numérisé](https://purl.stanford.edu/fz023dp4399), [fragment XML de contrôle](data/parents/lawastine-tiers.xml).

Références : `div2[14]/div3[9]`. Plage décodée du volume : `[1301246, 1304778)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:fz023dp4399:10c1f778fd324706de33`.

Motif : court ; numérotation ordinale.

Date de présentation : 1789-03-29. Provenance : p1 assemblée du 29 mars ; p8 renvoie à cette date.

Résultat : 5 candidats automatiques avant revue ; 5 A et 0 B après revue. 4 décisions de rôles/plages, hors annotations des unités de référence.

### colmar-ville

**Ville de Colmar**, volume 3 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml), [volume numérisé](https://purl.stanford.edu/mc666yy3026), [fragment XML de contrôle](data/parents/colmar-ville.xml).

Références : `div2[1]/div3[3]`. Plage décodée du volume : `[110342, 145872)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:mc666yy3026:7252b87cf6dd0d663706`.

Motif : article sans numéro ; sous-listes ; supplément ; sept initiaux.

Date de présentation : 1789-03-24. Provenance : p[57] : fait, lu et interprété ... le 24 mars 1789. La date balisée 27 avril en p[61] est une collation, pas la rédaction. Le div3 inclut aussi un supplément traduit de l’allemand en mai..

Résultat : 36 candidats automatiques avant revue ; 8 A et 28 B après revue. 8 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Supplément rédigé en allemand puis traduction française certifiée : source de mai distincte du corps de mars ; pas modernisation. Subdivisions du supplément non validées.

### ribaucourt

**Communauté de Ribaucourt**, volume 3 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml), [volume numérisé](https://purl.stanford.edu/mc666yy3026), [fragment XML de contrôle](data/parents/ribaucourt.xml).

Références : `div2[22]/div3[9]`. Plage décodée du volume : `[1757036, 1764576)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:mc666yy3026:f330cd449d20585043c2`.

Motif : numérotation ordinale ; communauté.

Date de présentation : 1789-03-18. Provenance : p15 Ainsi fait et arrêté.

Résultat : 10 candidats automatiques avant revue ; 11 A et 0 B après revue. 4 décisions de rôles/plages, hors annotations des unités de référence.

### flines

**Habitants de Flines**, volume 3 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml), [volume numérisé](https://purl.stanford.edu/mc666yy3026), [fragment XML de contrôle](data/parents/flines.xml).

Références : `div2[22]/div3[14]`. Plage décodée du volume : `[1852913, 1859588)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:mc666yy3026:97af66caeb2eea3e1442`.

Motif : articles sur plusieurs paragraphes.

Date de présentation : 1789-03-23. Provenance : p1 assemblée du 23 mars ; p17 jour mois an que dessus.

Résultat : 13 candidats automatiques avant revue ; 13 A et 0 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### carces-mineurs

**Frères mineurs de Carces**, volume 3 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml), [volume numérisé](https://purl.stanford.edu/mc666yy3026), [fragment XML de contrôle](data/parents/carces-mineurs.xml).

Références : `div2[24]/div3[9]`. Plage décodée du volume : `[2496436, 2502151)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:mc666yy3026:f9e19530b4e33ccf95c7`.

Motif : très court ; articles et signature.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 8 candidats automatiques avant revue ; 8 A et 0 B après revue. 1 décisions de rôles/plages, hors annotations des unités de référence.

### montigny-ostrevent

**Montigny en Ostrevent**, volume 3 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/mc666yy3026/mc666yy3026.xml), [volume numérisé](https://purl.stanford.edu/mc666yy3026), [fragment XML de contrôle](data/parents/montigny-ostrevent.xml).

Références : `div2[22]/div3[23]`. Plage décodée du volume : `[2030673, 2039539)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:mc666yy3026:5ef43e6dd0afce138d76`.

Motif : numérotation et titres fortement dégradés.

Date de présentation : 1789-03-02. Provenance : p21 lecture certifiée ; date de lecture, pas nécessairement rédaction.

Résultat : 15 candidats automatiques avant revue ; 11 A et 8 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Numérotation OCR très dégradée : conserver z8,36,B®,Il®, sans restaurer les chiffres ; frontières hors fenêtre non certifiées.

### mirecourt-noblesse

**Noblesse de Mirecourt**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/mirecourt-noblesse.xml).

Références : `div2[1]/div3[2]`; `div2[1]/div3[3]`; `div2[1]/div3[4]`. Plage décodée du volume : `[7726, 49457)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:b6a30344f86d9da9f1ea`.

Motif : deux articles dans un paragraphe ; demandes et travail annexes ; sept initiaux.

Date de présentation : 1789-03-16. Provenance : date[@value='1789-03-16'] dans head[2]..

Résultat : 25 candidats automatiques avant revue ; 13 A et 12 B après revue. 7 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Demandes provinciales et mémoire justificatif joints au dossier ; l’ancien parent ne couvrait que le premier div3. Annexe p2 sans marqueur non certifiée.

### guerande-tiers

**Tiers état de la sénéchaussée de Guérande**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/guerande-tiers.xml).

Références : `div2[9]/div3[3]`. Plage décodée du volume : `[904586, 926813)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:af71dbb9f75db8ce99b2`.

Motif : articles longs ; votes en liste ; sept initiaux.

Date de présentation : 1789-04-03. Provenance : p[45] : Clos et arrêté ... cedit jour 3 avril 1789 ; extraction manuelle sourcée..

Résultat : 27 candidats automatiques avant revue ; 8 A et 19 B après revue. 5 décisions de rôles/plages, hors annotations des unités de référence.

### ferrieres

**Tiers état de Ferrières en Brie**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/ferrieres.xml).

Références : `div2[18]/div3[145]`; `div2[18]/div3[146]`; `div2[18]/div3[147]`; `div2[18]/div3[148]`; `div2[18]/div3[149]`. Plage décodée du volume : `[5028040, 5034067)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:4133d7972888544d97cb`.

Motif : cinq divisions ; quatre sections ; reprise des numéros.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 25 candidats automatiques avant revue ; 24 A et 1 B après revue. 2 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Constitution art15 annonce les articles thématiques suivants ; statut hiérarchique à vérifier, pas de segmentation sémantique.

### annet-marne

**Annet-sur-Marne**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/annet-marne.xml).

Références : `div2[18]/div3[8]`. Plage décodée du volume : `[2705601, 2709736)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:eef09d567c9a82f751c0`.

Motif : articles ; clôture et signatures.

Date de présentation : 1789-04-13. Provenance : p18 Fait et arrêté.

Résultat : 15 candidats automatiques avant revue ; 15 A et 0 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### ermenonville

**Ermenonville / Arnouville**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/ermenonville.xml).

Références : `div2[18]/div3[12]`. Plage décodée du volume : `[2880253, 2882169)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:2d9eb8a19442dcf619d3`.

Motif : lieu ambigu dans la source ; Art. ler. OCR.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 12 candidats automatiques avant revue ; 12 A et 0 B après revue. 2 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Deux dénominations dans le titre ; aucune résolution géographique moderne.

### mirecourt-clerge

**Clergé de Mirecourt**, volume 4 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml), [volume numérisé](https://purl.stanford.edu/xg914wh0253), [fragment XML de contrôle](data/parents/mirecourt-clerge.xml).

Références : `div2[1]/div3[1]`. Plage décodée du volume : `[2312, 7705)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xg914wh0253:fbbba92b6bb96154d07a`.

Motif : numérotation ordinale ; certification.

Date de présentation : 1789-03-27. Provenance : p1 Du 27 mars 1789.

Résultat : 5 candidats automatiques avant revue ; 5 A et 0 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### pierrelez-habitants

**Habitants de Pierrelez**, volume 5 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml), [volume numérisé](https://purl.stanford.edu/xx284sn7328), [fragment XML de contrôle](data/parents/pierrelez-habitants.xml).

Références : `div2[1]/div3[9]`. Plage décodée du volume : `[194234, 196791)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xx284sn7328:12cdaced3d457962e532`.

Motif : neuf articles courts ; sept initiaux.

Date de présentation : 1789-04-14. Provenance : p[11] : fait le mardi 14 avril 1789 ; extraction manuelle sourcée, pas un attribut date..

Résultat : 9 candidats automatiques avant revue ; 9 A et 0 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### perigny-brie

**Tiers état de Périgny-en-Brie**, volume 5 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml), [volume numérisé](https://purl.stanford.edu/xx284sn7328), [fragment XML de contrôle](data/parents/perigny-brie.xml).

Références : `div2[1]/div3[5]`. Plage décodée du volume : `[124227, 129592)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xx284sn7328:0e4e17a10525b854d367`.

Motif : articles ; préambule dans le premier article.

Date de présentation : 1789-04-14. Provenance : p18 Fait et arrêté.

Résultat : 15 candidats automatiques avant revue ; 15 A et 0 B après revue. 4 décisions de rôles/plages, hors annotations des unités de référence.

### plessis-secqueville

**Tiers état du Plessis-Secqueville**, volume 5 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml), [volume numérisé](https://purl.stanford.edu/xx284sn7328), [fragment XML de contrôle](data/parents/plessis-secqueville.xml).

Références : `div2[1]/div3[18]`. Plage décodée du volume : `[279262, 283623)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xx284sn7328:83dfa5bae7397bf30538`.

Motif : court ; clôture et signatures.

Date de présentation : 1789-04-16. Provenance : p11 Fait délibéré et arrêté.

Résultat : 9 candidats automatiques avant revue ; 9 A et 0 B après revue. 3 décisions de rôles/plages, hors annotations des unités de référence.

### puteaux

**Habitants de Puteaux**, volume 5 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml), [volume numérisé](https://purl.stanford.edu/xx284sn7328), [fragment XML de contrôle](data/parents/puteaux.xml).

Références : `div2[1]/div3[29]`. Plage décodée du volume : `[440333, 447416)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:xx284sn7328:9a570b0100acb2734ded`.

Motif : onze articles ; demandes particulières ; observation additionnelle après signatures.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 11 candidats automatiques avant revue ; 11 A et 0 B après revue. 6 décisions de rôles/plages, hors annotations des unités de référence.

### vic-clerge

**Clergé du bailliage de Vie [graphie TEI]**, volume 6 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml), [volume numérisé](https://purl.stanford.edu/wg983ft3682), [fragment XML de contrôle](data/parents/vic-clerge.xml).

Références : `div2[1]/div3[4]`. Plage décodée du volume : `[140779, 162953)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:wg983ft3682:72447fb17ff8b4b6f261`.

Motif : articles ; collation ; sept initiaux.

Date de présentation : 1789-03-28. Provenance : date[@value='1789-03-28'] dans head[2] ; graphie du lieu conservée comme Vie..

Résultat : 42 candidats automatiques avant revue ; 8 A et 34 B après revue. 4 décisions de rôles/plages, hors annotations des unités de référence.

### toul-noblesse

**Noblesse de Toul et pays toulois**, volume 6 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml), [volume numérisé](https://purl.stanford.edu/wg983ft3682), [fragment XML de contrôle](data/parents/toul-noblesse.xml).

Références : `div2[1]/div3[2]`. Plage décodée du volume : `[38189, 70408)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:wg983ft3682:8dab1fac50b6320bcb33`.

Motif : très long ; préambule ; signatures nombreuses.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 34 candidats automatiques avant revue ; 2 A et 32 B après revue. 52 décisions de rôles/plages, hors annotations des unités de référence.

Limites : Demandes sans numéro et intitulés fréquents ; rattachement des rubriques hors fenêtres non certifié.

### albertas

**Habitants d’Albertas**, volume 6 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml), [volume numérisé](https://purl.stanford.edu/wg983ft3682), [fragment XML de contrôle](data/parents/albertas.xml).

Références : `div2[17]/div3[1]`. Plage décodée du volume : `[2107339, 2111031)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:wg983ft3682:c33d108ba660e47d2e75`.

Motif : articles courts ; clôture et signatures.

Date de présentation : 1789-03-22. Provenance : head assemblée générale.

Résultat : 9 candidats automatiques avant revue ; 9 A et 0 B après revue. 2 décisions de rôles/plages, hors annotations des unités de référence.

### beaurecueil

**Habitants de Beaurecueil**, volume 6 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml), [volume numérisé](https://purl.stanford.edu/wg983ft3682), [fragment XML de contrôle](data/parents/beaurecueil.xml).

Références : `div2[17]/div3[14]`. Plage décodée du volume : `[2345533, 2349561)`. Statut : `verified_xml_and_scan`. Identifiant : `ap1789-pilot-d1:wg983ft3682:f7df571f2f7d6b380e1b`.

Motif : prose puis trois demandes dans un même p ; deux cahiers dans un div3 ; note en p.

Date de présentation : non extraite de manière fiable. Provenance : Non extraite à ce stade ; aucune date inventée..

Résultat : 3 candidats automatiques avant revue ; 3 A et 0 B après revue. 2 décisions de rôles/plages, hors annotations des unités de référence.

Limites : La même division XML contient ensuite Belcodène (p9–15), exclu du parent ; clôture de Beaurecueil et signature dans p8.

### lourmarin

**Habitants de Lourmarin**, volume 6 — [XML source figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml), [volume numérisé](https://purl.stanford.edu/wg983ft3682), [fragment XML de contrôle](data/parents/lourmarin.xml).

Références : `div2[17]/div3[43]`. Plage décodée du volume : `[2881144, 2889905)`. Statut : `verified_xml`. Identifiant : `ap1789-pilot-d1:wg983ft3682:7b9e79cfa79fff18df92`.

Motif : prose ; certification ; titre coupé.

Date de présentation : 1789-03-29. Provenance : p11 certification ; ne pas confondre avec rédaction.

Résultat : 0 candidats automatiques avant revue ; 0 A et 0 B après revue. 4 décisions de rôles/plages, hors annotations des unités de référence.

