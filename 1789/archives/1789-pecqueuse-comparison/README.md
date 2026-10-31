# Pecqueuse : comparaison des TEI Stanford et Persée

Comparaison du 26 octobre 2026, limitée au cahier de Pecqueuse, tome V des *Archives parlementaires*, pages 10–12.

**Les deux transcriptions permettent d'identifier les 38 articles. Chacune en conserve 37 intégralement dans un seul paragraphe XML, mais pas les mêmes. Persée apporte surtout un identifiant de cahier et des métadonnées explicites ; aucun avantage décisif pour remplacer Stanford dans l'extraction des articles n'est démontré ici.**

## Sources et correspondance

- **Stanford** : fichier local `/tmp/cahier-1789-extraction-pilot/sources/xx284sn7328.xml`, déjà utilisé dans les audits ; [révision figée `926fd3cd986a3c3d411e93d1845fff6475cb2602`](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml). SHA-256 : `42bd670ff817d77e31f0ba02a9af811248dc0ecfe5786beb4829043c72e4bc44`, conforme à l'inventaire antérieur.
- **Persée** : TEI intégral **collé par l'utilisateur dans l'échange**, après signalement de l'absence du fichier local. Racine `xml:id="arcpa_0000-0000_1879_num_5_1_2333"`, titre « Cahier de Pecqueuse (Paris) », volume 5, pages 10–12. Analyse de ce XML, sans substitution par le HTML du portail et sans copie intégrale dans le dépôt. L'empreinte du fichier original et sa date d'export ne sont pas disponibles.
- **Contrôle imprimé** : PDF Persée local `~/Téléchargements/arcpa_0000-0000_1879_num_5_1_2333.pdf`, quatre pages : couverture bibliographique puis pages imprimées 10, 11 et 12. Ces trois images ont été examinées. [Référence du document](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2333).

La correspondance est confirmée par le titre, la suite des 38 articles, les signataires et le colophon daté du **13 avril 1789**. Chez Stanford, le cahier est `/TEI.2/text/body/div1/div2[1]/div3[3]`. Il est précédé de Pavaut et suivi du **Port-au-Pecq**, document distinct. Il ne s'agit pas de Pierrelez, dont l'identifiant Persée se termine par `2339`.

## Comparaison

| Critère | Stanford | Persée, TEI fourni |
|---|---|---|
| Cahier parent | Une `div3 type="other"`, sans identifiant propre | Un document TEI avec `xml:id` propre |
| Titre | `head` « CAHIER », puis intitulé complet dans `p[1]` | Titre documentaire complet dans l'en-tête ; intitulé transcrit du corps tronqué après « des habi¬ » |
| Articles reconnaissables | **38/38**, suite 1–38 | **38/38**, suite 1–38, avec « Art. 1 1 . » pour 11 |
| Articles complets dans un seul `p` | **37/38** | **37/38** |
| Article sur plusieurs `p` | **37**, réparti entre `p[39]` et `p[40]` | **24**, deux paragraphes de réponse séparés par un paragraphe de titre courant |
| Plusieurs articles dans un même `p` | Aucun | Aucun |
| Balisage d'article | Numérotation textuelle ; aucun élément ou ID d'article | Numérotation textuelle ; aucun élément ou ID d'article |
| Notes et signatures | Note éditoriale `note place="foot"` séparée ; signatures et certification en `p` | Note éditoriale séparée, avec ID ; signatures et certification en `p`, découpées par page |
| Pagination | Page 10 héritée du `pb` précédent ; `pb` 11 puis 12, ce dernier dans les signatures | Trois `pb` explicites 10/11/12 avec IDs de page ; divisions principalement par page |
| Métadonnées | En-tête de volume, titre et date dans le texte du cahier | Titre, identifiant, URL, volume, pages, éditeurs scientifiques et édition de 1879 structurés ; date de rédaction dans le texte |

**Définition du comptage** : « un seul paragraphe » signifie que le début et la fin du texte de l'article se trouvent dans un même `p`, sans fusion avec un autre article. Ce n'est ni un taux de fidélité OCR ni une validation automatique universelle. Les 38 articles occupent **39 paragraphes de texte d'article dans chaque source** ; les titres, notes, préambules et signatures sont comptés séparément. Comptage Stanford contrôlé par lecture XML et assertions ponctuelles ; comptage Persée effectué sur le XML fourni.

## Trois difficultés concrètes

1. **Délimiter le cahier au-delà de ses articles.** Le début se trouve dans la colonne droite de la page 10, après Pavaut. Les articles 1–6 sont page 10 ; les articles 7–38 et le paragraphe « Au surplus » sont page 11. Les signatures commencent page 11 et continuent page 12, suivies de la certification et de la signature de Rosnay. Les deux TEI respectent cette frontière et excluent Port-au-Pecq, qui commence sur la même page 12. La mention « contenant huit pages » décrit le cahier manuscrit, pas les trois pages de son édition imprimée.

2. **Reconstituer les paragraphes logiques.** Stanford coupe l'article 37 après « terres remises en » et place « valeur. ,. , » dans le paragraphe suivant : il faut les réunir. Persée conserve cet article entier, mais coupe l'article 24 après « qu'ils aient tous », intercale « ILEMENTAIRES. [Paris hors les murs.j », puis reprend « les moyens de faire connaître leur innocence. ». Le scan confirme une continuation entre colonnes, sans nouveau paragraphe documentaire : ce fragment d'en-tête doit être exclu. Persée contient aussi un début de titre courant avant l'article 7.

3. **Reconnaître les numéros sans corriger le texte.** Stanford écrit `Art'. 29.` et omet le point après `Art. 37` ; Persée écrit `Art. 1 1 .` pour l'article 11. La suite complète rend ces repères identifiables, mais une expression régulière exigeant exactement `Art. 11.` échouerait. L'article 1 Stanford contient en outre `1<hi rend="superscript">er</hi>` : lire uniquement le nœud texte initial perdrait une partie du repère. Aucun de ces constats ne justifie une correction silencieuse du témoin original.

## OCR : contrôles ponctuels sur les images

| Emplacement | Stanford | Persée TEI | Lecture de l'imprimé |
|---|---|---|---|
| Préambule, p. 10 | `en Rassemblée` | `eq l'assemblée` | `en l'assemblée` : les deux transcriptions sont fautives |
| Article 5, p. 10 | `movennant` | `moyennant` | `moyennant` : avantage Persée sur ce mot |
| Article 31, p. 11 | `seules` | `seuies` | `seules` : avantage Stanford sur ce mot |
| Même article, p. 11 | `sans qu’aucun autre quelle` | `sans qu'aucun autre qu'elle` | `qu'elle` : avantage Persée sur cette lecture |

Persée conserve aussi de nombreuses coupures `¬` suivies d'espaces, par exemple `cha¬ cun` à l'article 3, alors que Stanford donne `chacun`. Son intitulé de corps perd la suite visible « tants de la paroisse de Pecqueuse (1). ». Ce sont des difficultés de transcription et de recomposition, distinctes de la langue historique. Ces exemples ciblés **ne mesurent pas une qualité OCR globale**.

## Traçabilité et conclusion opérationnelle

Persée facilite le rattachement au **document parent**, à sa référence bibliographique et à ses pages. Les divisions des pages 10 et 12 possèdent des IDs, mais celle de la page 11 n'en possède pas ; les paragraphes d'articles n'ont pas d'ID. Stanford offre la révision Git, l'empreinte du volume, un XPath reproductible et les vues `xx284sn7328_00_0014` à `0016` ([volume numérisé](https://purl.stanford.edu/xx284sn7328)). Pour les deux sources, les positions et identifiants d'articles restent à construire de manière traçable. La date **1879** des métadonnées Persée est celle de l'édition, pas celle de la rédaction.

**Réponse à la question principale : sur Pecqueuse, l'avantage Persée est réel pour les métadonnées, mais insuffisant pour justifier un remplacement de Stanford comme source d'extraction textuelle.** Le nombre d'articles directement contenus dans un paragraphe est identique ; Persée corrige certaines lectures mais ajoute des coupures, une perte de titre et une pollution de l'article 24. Conserver Stanford comme témoin principal et considérer Persée comme appui documentaire est raisonnable sur cet exemple. Une supériorité générale nécessiterait d'autres comparaisons, non réalisées ici.

L'en-tête du TEI Persée indique une restriction de téléchargement/impression à l'usage personnel ; le fichier transmis pour l'étude n'établit pas une autorisation de republication. Ce point reste à clarifier avant un usage public. Aucun TEI Persée intégral, PDF ou image n'est ajouté au dépôt ; seul ce rapport est créé. Aucun accès à PostgreSQL ni changement applicatif, et les audits précédents restent inchangés.
