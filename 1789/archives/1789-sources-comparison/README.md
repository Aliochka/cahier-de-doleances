# Comparaison des sources numériques des cahiers de 1789

Étude du 25 octobre 2026, en complément de l’[audit Stanford et multicorpus](../1789-multicorpus/README.md), lu intégralement avant cette comparaison. Les fichiers de ce premier audit sont conservés sans modification.

**Recommandation : conserver Stanford comme témoin textuel principal pour la prochaine extraction expérimentale. Persée apporte un gain documentaire démontré pour le catalogue et certains regroupements, mais son texte HTML ne remplace pas avantageusement Stanford sur tous les passages. Le service ARTFL consulté ne montre aucune correction du texte des sept cahiers comparés.**

Il n’y a pas de source démontrée supérieure sur tous les critères. Une combinaison limitée, Stanford pour le texte et Persée pour des références documentaires vérifiées, est une piste utile ; sa republication et son automatisation restent conditionnées à la clarification des droits et à la validation des correspondances. Aucun assemblage automatique de corrections OCR n’est recommandé.

## 1. Périmètre, méthode et résultats mesurés

La comparaison réutilise les sept cahiers du premier audit, répartis dans les volumes 1–6, ainsi que ses exemples difficiles d’Albret et de Ferrières. Aucun corpus supplémentaire n’a été collecté en masse.

Ont été consultés/téléchargés dans `/tmp/cahier-1789-source-comparison` : les pages descriptives des producteurs ; le catalogue bibliographique ARTFL (83 entrées), les tables des matières des six premiers volumes et sept fragments de cahiers ; quelques fragments structurels de contrôle ; les sept notices et les **27 fragments HTML de pages** de ces cahiers chez Persée ; sept notices MODS et un METS de volume ; cinq images Persée pour contrôle visuel. Les images et réponses intégrales restent dans cet espace temporaire. L’étude livre les observations, mesures, références, empreintes et scripts d’analyse, sans republier les images ou les réponses intégrales des services.

Le texte Stanford provient du snapshot figé `926fd3cd986a3c3d411e93d1845fff6475cb2602` et des extraits du premier audit, sans nouveau téléchargement des 83 volumes.

Trois résultats quantitatifs doivent être distingués :

1. **497/497 paragraphes identiques entre Stanford et ARTFL**, dans les sept cahiers, après réduction des seuls blancs. Accents, lettres, ponctuation, traits d’union et nombres n’ont pas été normalisés pour ce contrôle. Cela couvre les `p` directs des divisions, y compris leurs signatures et autres paragraphes ; ce ne sont pas 497 revendications et cela ne compare pas tout le balisage, les titres ou les notes. Aucun gain OCR n’est démontré dans ce périmètre du service actuel.
2. **Cinq anomalies connues contrôlées ponctuellement**, avec transcription de référence lue sur les scans : quatre unités courtes sont conformes à cette référence chez Persée, contre aucune chez Stanford/ARTFL. La cinquième, « liberté », reste erronée dans les deux transcriptions. Ce choix volontairement orienté vers des défauts Stanford n’est pas un taux de précision du corpus.
3. **Deux contrôles de complétude négatifs dans le HTML Persée** : les passages recherchés d’Angoumois, page 3, et le début de l’article 1 de Colmar, page 12, sont visibles sur les images et présents chez Stanford/ARTFL, mais absents des fragments HTML récupérés. Cela ne démontre pas leur absence dans un export TEI réservé que nous n’avons pas obtenu.

Les résultats calculés sont dans [data/metrics.json](data/metrics.json), les 497 paires d’empreintes dans [data/paragraph-pairs.json](data/paragraph-pairs.json), les cinq contrôles dans [data/probes.json](data/probes.json) et les omissions observées dans [data/completeness-controls.json](data/completeness-controls.json).

## 2. Tableau comparatif

| Critère | Stanford `ap_tei` | ARTFL / French Revolutionary Data | Persée |
|---|---|---|---|
| Accès effectivement vérifié | XML local du premier audit, dépôt Git et révision figée | Catalogue et fragments JSON/HTML par PhiloLogic5 ; pas d’archive TEI corrigée localisée | Pages et fragments HTML, MODS OAI et METS de volume accessibles ; Perséide spécialisée en erreur |
| Cahiers des volumes 1–6 | Présents ; sept divisions déjà étudiées | Six premiers fichiers explicitement dans le catalogue ; sept cahiers récupérés | Sept cahiers retrouvés dans six volumes ; titres distincts et plages de pages |
| Formats obtenus | TEI P4 XML | JSON du service contenant HTML dérivé de TEI, en-tête TEI échappé | HTML du document et de ses pages, MODS/METS XML, BibTeX ; images JPEG |
| OCR observé | Défauts de référence du premier audit | 497 paragraphes identiques à Stanford ; les cinq anomalies ciblées persistent | Corrections ponctuelles, autres erreurs et omissions HTML ; supériorité globale non établie |
| Cahier parent | À reconstituer selon les divisions et pièces annexes | `type=cahier` et identifiants PhiloLogic ; mêmes divisions sur les sept cahiers | Identifiant documentaire explicite ; regroupements plus larges de certaines sections |
| Articles | Numérotation textuelle à interpréter | Numérotation et paragraphes inchangés dans les exemples ; pas d’ID d’article relevé | Numérotation dans les paragraphes HTML ; paragraphes parfois fusionnés, pas d’ID d’article relevé |
| Métadonnées | En-tête de volume, titres, dates locales, pages | Titres fusionnés, type, date remontée dans les métadonnées ; erreurs et ambiguïtés subsistent | Titres éditoriaux, type documentaire, volume, pages, URL, hiérarchie territoriale ; ordre/localité surtout dans les titres |
| Traçabilité | Révision Git, empreintes, fichier, XPath, Druid/page | Réponse et build courants ; ID de navigation et `facs` ; pas de version immuable de corpus annoncée dans les réponses | ID de document, OAI datestamp, plages de pages et références bibliographiques ; pas de positions d’articles comparables aux offsets Stanford |
| Réutilisation | Déclaration de domaine public des volumes ; portée des droits numériques à clarifier | Licence CC0 sur le dépôt du site, non transposable automatiquement aux textes du service externe | CGU et notice MODS à clarifier pour republication ; export de contenu réservé aux utilisateurs identifiés |
| Intégration estimée | Moyenne : segmentation documentaire à valider, conservation simple des témoins | Moyenne à forte pour une collecte pérenne sans archive documentée ; pas de gain textuel observé justifiant un remplacement | Faible à moyenne pour aider au catalogue ; forte/incertaine pour remplacer tous les textes sans export contrôlé et accord de réutilisation |

Les niveaux de difficulté sont des estimations de conception, sans développement applicatif. « Accessible » désigne une possibilité technique vérifiée, pas une autorisation de republier.

## 3. ARTFL : données réellement accessibles et portée des améliorations

### Parcours vérifié

La page [French Revolutionary Data](https://frenchrevdata.github.io/) annonce des textes nettoyés par ARTFL. Le HTML publié et l’arbre Git du dépôt `frenchrevdata.github.io` ont été examinés : pas de répertoire de cahiers XML ni de lien d’archive de données trouvé. Le dépôt contient le site, sa documentation et son thème. Les dépôts officiels examinés `frenchrevdata/ap`, `ap-analytics` et `ap-evaluation-digital-artifact` contiennent des scripts de recherche/évaluation, sans fichiers TEI de volumes dans leurs arbres inspectés. `ocrerrors.py` travaille sur un dossier local `AP_ARTFL_vols/` : ce chemin n’est pas une URL de téléchargement ni la preuve d’une diffusion des fichiers.

La [page officielle ARTFL des Archives parlementaires](https://artfl-project.uchicago.edu/archives-parlementaires) mène en revanche à un service fonctionnel :

- [Interface PhiloLogic5 `archparl`](https://artflsrv04.uchicago.edu/philologic5/archparl/).
- [Catalogue JSON des volumes](https://artflsrv04.uchicago.edu/philologic5/archparl/scripts/get_bibliography.py?object_level=doc).
- [Configuration publique](https://artflsrv04.uchicago.edu/philologic5/archparl/scripts/get_web_config.py).
- Exemple de [table des matières du volume IV, ID de service 6](https://artflsrv04.uchicago.edu/philologic5/archparl/scripts/get_table_of_contents.py?philo_id=6).
- Exemple de [réponse de navigation du cahier de Mirecourt](https://artflsrv04.uchicago.edu/philologic5/archparl/reports/navigation.py?report=navigation&philo_id=6%202%202%203).

Ces requêtes sont celles utilisées par le client public ; leurs URL ont été relevées dans son JavaScript, pas déduites d’une API privée. Elles retournent des fragments consultables et sauvegardables. Elles ne sont pas présentées ici comme une API d’export pérenne et contractuellement autorisée pour une republication massive.

### Couverture réellement constatée

Le catalogue retourne **83 entrées**, avec `APvol01.tei` à `APvol82.tei` et dédoublement du volume 71. Les six premiers volumes sont inclus. Leurs identifiants de service sont respectivement **2, 4, 5, 6, 1, 3** : ne pas confondre ID PhiloLogic et numéro de tome. Les noms, titres et identifiants sont conservés dans [data/coverage.json](data/coverage.json).

Les sept cahiers ont été retrouvés en contrôlant territoire, titre, ordre et texte, puis les 497 paragraphes ont été appariés dans l’ordre. On peut donc comparer les textes eux-mêmes ; l’annonce d’un nettoyage n’est plus le seul élément disponible.

**Aucune des cinq anomalies ciblées n’a été corrigée dans cette représentation ARTFL.** Ce résultat ne réfute pas l’existence de corrections ailleurs dans le corpus, d’une autre version de travail ou d’un autre export. Il interdit seulement de promettre un meilleur OCR des cahiers sur la base de cette version consultée.

### Balisage : améliorations réelles, portée limitée

Les sept divisions sont annoncées `type=cahier`. Les titres précédemment répartis entre plusieurs `head` sont regroupés dans le rendu. Des dates sont remontées en `div_date`. C’est un enrichissement utile du contrat de consultation.

Deux contrôles empêchent d’en déduire une segmentation documentaire fiable :

- La notice de cahier introuvable d’Albret est elle aussi `type=cahier` (ID `2 2 8 2`).
- Le chapitre II du clergé d’Anjou est une division `type=cahier` distincte (ID `4 2 3 3`), comme Constitution et Agriculture de Ferrières (IDs `6 2 19 146` et `147`). Le début de Ferrières est `6 2 19 145`. Le type n’évite donc pas la reconstruction du parent.

À Colmar, `div_date=1789-04-27` correspond toujours à la collation ; la rédaction/lecture du cahier est mentionnée au 24 mars dans le texte. Des titres de volumes II, III et VI restent affichés comme « TOME PREMIER » dans les métadonnées bibliographiques du service. La vérification par fichier et contenu reste nécessaire.

Les IDs PhiloLogic repèrent des objets dans un build ; rien dans les réponses reçues ne garantit leur stabilité lors d’un réindexage. Les paragraphes HTML examinés n’ont pas d’identifiant documentaire d’article. Les images utilisent les mêmes identifiants de vues Stanford, via des chemins `APvolXX/{druid}_00_....jpg`, ce qui facilite le rapprochement au niveau page.

### Limites d’accès et méthode pour obtenir la suite

L’essai ciblé du chemin `data/TEXT/APvol01.tei` sur le service ARTFL a répondu HTTP 200 avec **la page HTML de l’application**, pas un XML. Un essai équivalent sur l’instance Stanford PhiloLogic a renvoyé HTTP 500. Aucun de ces essais ne prouve l’absence des fichiers sur les serveurs. Les réponses et leur type de contenu sont documentés dans [data/access-log.json](data/access-log.json).

Pour lever le point restant, demander après validation à ARTFL/Stanford l’archive TEI précise annoncée, sa date/révision, la liste des volumes, les transformations appliquées aux volumes 1–6 et la licence applicable à ces fichiers. Joindre les cinq références ciblées et les IDs ci-dessus pour identifier sans ambiguïté une autre version éventuelle. Aucun contact n’a été envoyé pendant cette mission.

## 4. Persée : consultation, texte et exports sont distincts

### Accès obtenu

Le portail `www.persee.fr` fonctionne pour les sept cahiers. La page initiale contient seulement le texte de la première page ; les suivantes sont chargées par les URL `data-content-url`. Il faut donc comparer les **fragments de pages**, sans prendre le HTML initial pour le texte intégral.

Exemple vérifié pour Pierrelez :

- [Document parent](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2339).
- [Fragment de page 21](https://www.persee.fr/doc/page/arcpa_0000-0000_1879_num_5_1_2339/arcpa_0000-0000_1879_num_5_1_T1_0021_0000).
- [Métadonnées MODS via OAI](https://oai.persee.fr/oai?verb=GetRecord&metadataPrefix=mods&identifier=oai:persee:article/arcpa_0000-0000_1879_num_5_1_2339).
- [Référence BibTeX](https://www.persee.fr/docAsBibTex/arcpa_0000-0000_1879_num_5_1_2339.bib).

Les fragments exposent `div.text[itemprop=articleBody]`, ses paragraphes et le lien à l’image. Leur page image est complète et peut inclure d’autres cahiers ; le texte du fragment est sélectionné pour le document parent, avec les imperfections de sélection observées ci-dessous. On ne peut pas remplacer une borne documentaire par la simple appartenance à une page commune.

### Exports vérifiés

La [documentation OAI officielle](https://www.persee.fr/entrepot-oai) distingue les métadonnées publiques de l’export des contenus réservé aux utilisateurs identifiés. Les sept `GetRecord` MODS ont fonctionné. Un `ListMetadataFormats` sur Pierrelez annonce `oai_dc`, `mods`, `marc`, `persee_dc`, sans format de texte intégral TEI public dans cette réponse.

Le [METS du tome IV](https://oai.persee.fr/oai?verb=GetRecord&metadataPrefix=persee_mets&identifier=oai:persee:issue/arcpa_0000-0000_1879_num_4_1) a également été obtenu : hiérarchie des territoires et **347 entrées `TYPE=griev`**, avec IDs de cahiers, ordre, titres et liens OAI/documents. Ce nombre décrit ce catalogue de volume, pas un nouveau nombre de cahiers uniques validés. Il n’est pas comparable directement au compte de titres Stanford commençant par CAHIER.

Le METS inspecté ne contient pas les articles de chaque cahier : il décrit le catalogue du volume. Les `FLocat` qui ont `MIMETYPE=text/xml` pointent notamment vers une notice Dublin Core ; **text/xml ne signifie pas transcription TEI intégrale**. Le PDF est proposé en consultation avec un mécanisme de captcha ; aucun contournement ni téléchargement automatisé du PDF n’a été tenté.

### Découpage utile, mais non équivalent au Stanford

- Les sept cahiers possèdent un ID et une référence propres. Les titres documentaires sont plus faciles à exploiter que de nombreux « CAHIER » isolés de Stanford.
- Mirecourt, noblesse, couvre **pages 1–6** chez Persée : cahier, demandes particulières et travail complémentaire sont regroupés. La division de l’échantillon Stanford/ARTFL ne couvrait que le cahier initial, suivi de divisions voisines. C’est une correspondance **un parent Persée vers plusieurs divisions Stanford**, pas une divergence à corriger en écrasant une version.
- En contrôle complémentaire, [Ferrières-en-Brie](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2175), pages 545–546, réunit le préambule et la section Constitution sous un même document. Stanford/ARTFL les séparent au même niveau. Le HTML montre un titre `h3` Constitution : gain de hiérarchie démontré, sans preuve d’identifiants stables pour chacun des articles.
- Pierrelez garde une limite claire, avec neuf articles puis date et signatures, malgré le cahier suivant situé sur la même page image.

La structure des **articles** reste à reconstruire : plusieurs sont dans un même paragraphe, un article peut continuer sur la page suivante, les notes et titres courants peuvent s’intercaler. Les paragraphes des fragments inspectés ne possèdent pas d’IDs d’articles. Un export TEI réservé pourrait contenir davantage d’informations : sa structure n’a pas été examinée et ne doit pas être présumée.

### Services non accessibles

La Perséide `archives-parlementaires.persee.fr` renvoie encore 403, y compris pour une page de catalogue ciblée. Une URL de l’infrastructure Persée `bibracte.persee.fr`, trouvée dans les résultats publics, échoue avec une discordance du certificat TLS ; celle-ci n’a pas été ignorée. Ces échecs ne concernent ni les sept pages classiques ni les services OAI qui ont fonctionné.

Suite concrète : utiliser le catalogue METS pour identifier les documents, puis demander un accès identifié à l’export de contenu des sept cahiers, avec documentation du TEI, version et conditions de republication/indexation. Vérifier alors les omissions HTML sur cet export, sans présumer qu’elles s’y reproduisent. Pas de contact envoyé et pas d’essai d’accès au contenu réservé.

## 5. Les sept documents identiques : références et écarts

Le tableau porte sur le même noyau documentaire, avec des extensions de limites explicites. Les liens de chaque ligne et les fragments de pages permettent de vérifier les observations. Les références et métadonnées machine sont dans [data/documents.json](data/documents.json).

| Cahier du premier audit | ARTFL, objet du service actuel | Persée, ID final et pages | Constats sur les dix critères demandés |
|---|---|---|---|
| Agen, clergé, t. 1 | [2/2/6/2](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/2/2/6/2) | [1529, 675–679](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_1_1_1529) | Texte ARTFL identique dans 182 p. Persée corrige le mot du sous-titre mais altère le titre de section en `B’ÀfrEN`. Articles/étiquettes souvent séparés, numérotation par sections à préserver. Notes et titres courants présents dans le flux HTML. Page et parent explicitement liés ; fin et signatures repérées. |
| Angoumois, noblesse, t. 2 | [4/2/2/3](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/4/2/2/3) | [1559, 3–7](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1559) | 101 p identiques Stanford/ARTFL, dont mots coupés. Le fragment Persée de page 3 ne contient que le long titre, alors que le scan porte aussi les articles 1–4 et une partie de la charte. Les pages suivantes donnent la suite. Le parent, le titre éditorial, les pages et la bibliographie sont utiles, mais le texte accessible est incomplet sur cette page. |
| Colmar, ville, t. 3 | [5/2/2/4](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/5/2/2/4) | [1795, 12–15](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_3_1_1795) | 83 p identiques Stanford/ARTFL. Persée restitue Art. 3 et « de fixer », mais omet le début de l’article 1. Sous-listes et continuations conservées avec divisions variables. Supplément et certifications restent dans le même ensemble ; date ARTFL de collation à distinguer de la rédaction. Images et référence de pages accessibles. |
| Mirecourt, noblesse, t. 4 | [6/2/2/3](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/6/2/2/3) | [1745, 1–6](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1745) | 15 p du noyau initial identiques. Persée sépare 1°/2° mais lit `libërté` à l’article 5. Article 4 encore coupé par la page ; notes et titres courants à traiter. Regroupement des pièces complémentaires dans le parent Persée. La date 16 mars est visible dans le texte et remontée chez ARTFL ; MODS donne l’édition 1879. |
| Pierrelez, habitants, t. 5 | [1/2/2/10](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/1/2/2/10) | [2339, 21](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_5_1_2339) | 12 p identiques. Persée conserve les neuf articles mais regroupe 6–8 dans un seul p, introduit des césures `¬` et des différences dans les noms des signataires. Titre, date de clôture et limite avec le cahier voisin retrouvés ; pas d’ordre explicite à inventer. Parent, page et bibliographie accessibles. |
| Vic, clergé, t. 6 | [3/2/2/5](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/3/2/2/5) | [2497, 16–18](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_6_1_2497) | 58 p identiques ; `Art. 2.11` subsiste chez ARTFL. Persée lit `Art. 2. Il` ; son titre éditorial donne Vic, mais le corps garde Vie et le titre imprimé du cahier manque dans le fragment de page 16 récupéré. Le scan porte Vic. Date 28 mars remontée chez ARTFL ; parent Persée classé sous Toul, à ne pas confondre avec le bailliage indiqué par le titre du texte. |
| Guérande, tiers état, t. 4 | [6/2/10/4](https://artflsrv04.uchicago.edu/philologic5/archparl/navigate/6/2/10/4) | [1780, 103–105](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_1780) | 46 p identiques, liste de votes comprise. Fragments Persée avec articles et continuations, mais coupures et erreurs comme `Sressiondu` ou `su ppression`. Le HTML initial consulté pouvait omettre des paragraphes de la page 103 que son fragment de page expose : vérifier le bon endpoint. Texte, signatures et date 3 avril dans le document ; titre éditorial et rattachement à Nantes distincts de la sénéchaussée d’origine. |

Ni « habitants » ni un regroupement éditorial sous un territoire n’autorise à déduire automatiquement un ordre ou une juridiction moderne. Les métadonnées doivent conserver leur provenance.

## 6. Comparaisons précises sur les textes et les scans

### Cinq contrôles ciblés

La référence est l’édition imprimée visible, sans modernisation. Les cellules reproduisent les unités effectivement lues ; la casse du titre est conservée à l’affichage. Pour la distance seulement : réduction des blancs, puis `casefold`, sans suppression des accents, des traits d’union ou des caractères incorrects. La distance de Levenshtein compte insertions, suppressions et substitutions en points de code Unicode.

| Référence imprimée / lieu | Stanford | ARTFL | Persée | Distances Stanford / ARTFL / Persée |
|---|---|---|---|---|
| `sénéchaussée`, sous-titre d’Agen | `sénéchaus8ée` | `sénéchaus8ée` | `SÉNÉCHAUSSÉE` | 1 / 1 / 0 |
| `de`, Colmar art. 2, « en ayant soin de fixer » | `ae` | `ae` | `de` | 1 / 1 / 0 |
| `Art. 3.`, Colmar | `Art.` | `Art.` | `Art. 3.` | 3 / 3 / 0 |
| `liberté`, Mirecourt art. 5 | `libdrté` | `libdrté` | `libërté` | 1 / 1 / 1 |
| `Art. 2. Il`, Vic | `Art. 2.11` | `Art. 2.11` | `Art. 2. Il` | 3 / 3 / 0 |

**Mirecourt n’est donc pas une correction exacte de « liberté » chez Persée.** Un mauvais caractère a été remplacé par un autre ; sur cette unité et cette métrique, la distance n’améliore pas le résultat. Ce constat évite de confondre ressemblance visuelle d’un mot et correction vérifiée.

Les contextes complets, numéros de paragraphes et URL des pages sont dans [data/probes.json](data/probes.json). Scans utilisés : Agen, référence du premier audit ; [Colmar p. 12](https://www.persee.fr/renderPage/arcpa_0000-0000_1879_num_3_1_1795/arcpa_0000-0000_1879_num_3_1_T1_0012_0000_710.jpg) ; [Mirecourt p. 2](https://www.persee.fr/renderPage/arcpa_0000-0000_1879_num_4_1_1745/arcpa_0000-0000_1879_num_4_1_T1_0002_0000_710.jpg) ; [Vic p. 16](https://www.persee.fr/renderPage/arcpa_0000-0000_1879_num_6_1_2497/arcpa_0000-0000_1879_num_6_1_T1_0016_0000_710.jpg).

Ces cinq contrôles constituent un diagnostic ciblé, pas un CER/WER global. Aucun pourcentage d’extractibilité ou de correction du corpus n’est extrapolé. La mesure 497/497 porte sur la concordance des deux transcriptions, pas sur leur vérité par rapport à l’imprimé.

### Deux pertes de contenu observées chez Persée

**Angoumois, page 3.** Stanford et ARTFL conservent `Art. 1er. Proposeront en premier lieulesdits dépu-`, puis `tés d’adresser…` dans le paragraphe suivant : contenu présent, segmentation et OCR imparfaits. Le [fragment Persée de cette page](https://www.persee.fr/doc/page/arcpa_0000-0000_1879_num_2_1_1559/arcpa_0000-0000_1879_num_2_1_T1_0003_0000) ne contient qu’un paragraphe de titre. L’[image](https://www.persee.fr/renderPage/arcpa_0000-0000_1879_num_2_1_1559/arcpa_0000-0000_1879_num_2_1_T1_0003_0000_710.jpg) montre le début de l’article en bas de colonne gauche, sa suite en haut de colonne droite, puis les articles 2, 3, 4 et la charte. Une correction locale des lettres ne compenserait pas cette perte de contenu dans le HTML obtenu.

**Colmar, page 12.** Le scan porte `Art. 1er. Les députés des dix villes d’Alsace supplieront…`. Stanford/ARTFL conservent le début ; le [fragment Persée](https://www.persee.fr/doc/page/arcpa_0000-0000_1879_num_3_1_1795/arcpa_0000-0000_1879_num_3_1_T1_0012_0000) commence ce paragraphe directement par `supplieront Sa Majesté…`. Le numéro et le sujet de la phrase sont perdus dans cette représentation accessible.

Ces observations sont répétées dans les fragments explicitement liés par le portail, pas seulement dans des extraits de moteur de recherche. Elles ne doivent pas être attribuées sans preuve à l’export TEI complet ou au PDF.

### Paragraphes et notes : pas de victoire uniforme

- **Mirecourt 1°/2°** : un `p` Stanford/ARTFL contient deux numéros ; Persée les sépare en deux `p`. Gain déterministe réel pour ce cas.
- **Pierrelez 6/7/8** : trois `p` Stanford/ARTFL deviennent un seul `p` Persée : « Art. 6. … Art. 7. … Art. 8. … ». Une règle de numérotation reste nécessaire, malgré la qualité du parent.
- **Césures** : Stanford/ARTFL conservent des `con- firmée`, `dépu-`/`tés` ; Persée utilise fréquemment `¬` avec espace, par exemple `diffi¬ culté` à Pierrelez. Ce sont des différences de transcription et de restitution de fin de ligne, pas une modernisation de langue. Une forme de recherche éventuellement décésurée devra être dérivée, sourcée et séparée du témoin affiché.
- **Notes** : Stanford les distingue par `note place=foot`, ARTFL les rend en `note-content` avec un contrôle de consultation ; le flux HTML Persée peut inclure notes et titres courants comme paragraphes ordinaires. Les formats publics comparés ne dispensent pas de distinguer le texte des demandes, les notes et les signatures.
- **Titres** : Persée offre des titres éditoriaux de catalogue utiles ; ils ne remplacent pas les intitulés historiques exacts. À Vic, le titre du catalogue est informatif alors que le titre imprimé manque dans le fragment textuel reçu ; les deux niveaux doivent rester distincts.

## 7. Métadonnées et traçabilité comparées

| Champ | Stanford | ARTFL observé | Persée observé |
|---|---|---|---|
| Localité | Texte des titres ; pas de champ systématique | Repris dans les titres fusionnés, pas de champ géographique dédié relevé | Souvent titre éditorial ; pas de coordonnées ou code communal relevé dans les sept MODS |
| Bailliage / sénéchaussée | Division de contexte et titre | Citation hiérarchique div2/div3 ; contexte parfois plus large que le lieu du cahier | METS territorial et titre ; vérifier le rôle de chaque territoire |
| Ordre | Souvent titre/sous-titre | Dans le titre ; pas de facette d’ordre autonome trouvée dans la configuration | Dans les titres de plusieurs notices, pas de champ d’ordre autonome relevé dans MODS |
| Date de rédaction | Balisage ou prose à interpréter | `div_date` pour trois cahiers : Mirecourt, Vic, Colmar ; Colmar est une collation | Texte consultable, mais `DC.date` et date MODS 1879 désignent l’édition, pas la rédaction |
| Titre du cahier | Morcelé entre head/p selon cas | Fusion de titres utile, mais OCR inchangé | Titre documentaire distinct, souvent plus explicite ; titre du texte conservé séparément dans le rendu lorsqu’il est présent |
| Volume / pagination | Mapping et pb, parfois étiquette vide | Nom `APvolXX.tei`, objets et images ; titre de volume parfois faux | Volume, début/fin de pages en MODS ; images et page IDs |
| Identifiant | Druid du volume, XPath du cahier et extraction versionnée | `philo_id` d’objet, dépendance au build ; IDs source vides dans les métadonnées examinées | ID de cahier, URL, identifiant OAI, datestamp de notice |
| Numérisation | IIIF Stanford, identifiant de vue | Chemin d’image reprenant les mêmes identifiants de vues | `renderPage` et lien de fragment ; correspondance par tome/page, pas par numéro de vue Stanford |
| Bibliographie | En-tête du tome et notes historiques | Métadonnées de volume et citation de navigation | Notice MODS, références affichées, BibTeX/RIS ; précision variable, certaines notices omettent éditeur/direction |

Les sept appariements sont étayés par le volume, les pages, le titre et la concordance des contenus. **L’identité de page n’est pas l’identité d’un article ou d’un cahier.** Les éditions et tirages doivent être vérifiés sur les pages de titre avant une correspondance globale ; le premier audit relève l’édition Stanford de 1879 et les références Persée examinées indiquent aussi 1879.

Les droits et déclarations de source font partie de la provenance ; conserver pour chaque objet la date de récupération, l’URL, le SHA-256 de la réponse, le producteur, les sélecteurs et la version d’extraction. Le `datestamp` d’une notice OAI ne suffit pas à dater le texte OCR sous-jacent. Les résultats PhiloLogic consultés ne fournissent pas de révision Git du corpus comparable au snapshot Stanford.

## 8. Conditions de réutilisation

Cette section distingue des déclarations constatées ; elle ne conclut pas à une licence générale à partir de la disponibilité publique ou du seul âge des textes.

| Couche | Stanford | ARTFL / French Revolutionary Data | Persée |
|---|---|---|---|
| Textes historiques et édition du XIXe siècle | README déclarant les volumes dans le domaine public | Même édition de base pour les passages comparés ; ne pas confondre texte et enrichissements | Ancienneté du texte distincte des conditions des ressources numériques |
| Transcription numérique | Pas de licence numérique séparée clairement définie dans le snapshot examiné | Aucune licence de republication propre aux réponses du service trouvée dans les pages/configuration/en-tête inspectés | Accès au texte dans le portail ; modalités d’export et de réutilisation à convenir pour l’usage du projet |
| Balisage XML | Dépôt public, portée exacte de la déclaration à clarifier | Pas d’archive TEI corrigée obtenue ; la licence du logiciel PhiloLogic ne couvre pas automatiquement les corpus | TEI de contenu non obtenu ; OAI de contenu réservé aux utilisateurs identifiés |
| Métadonnées | Attribution et conditions à conserver | Licence CC0 présente dans le dépôt du site `frenchrevdata.github.io`, qui ne contient pas les transcriptions du service externe | MODS/METS ouverts techniquement ; CGU et restriction MODS à clarifier pour une reprise sur un autre site |
| Images | Déclarations des manifestes du premier audit, sans licence de redistribution explicite | Hébergement d’images ne constitue pas une licence distincte de republication | Consultation via `renderPage`, sans licence ouverte d’image relevée sur les fragments examinés |

Sources : [README Stanford figé](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/README.txt), [notice de droits Stanford Libraries](https://library.stanford.edu/copyright-notice), [dépôt du site French Revolutionary Data](https://github.com/frenchrevdata/frenchrevdata.github.io), [CGU Persée](https://www.persee.fr/cgu), [documentation de l’entrepôt OAI](https://www.persee.fr/entrepot-oai).

**Point supplémentaire vérifié chez Persée :** les sept notices MODS contiennent une condition autorisant téléchargement et impression pour usage personnel, avec renvoi aux restrictions générales. Par ailleurs, les CGU §5/§12 encadrent les services et jeux de données pour des finalités non commerciales et prévoient attribution/origine. La valeur HTML `DC.rights=free` n’annule pas ces conditions et ne constitue pas une licence ouverte de republication. La portée respective de ces déclarations doit être clarifiée pour cahierdedoleances.fr, y compris si le site est gratuit.

**Point supplémentaire vérifié pour ARTFL :** le `LICENSE` CC0 du dépôt de la page d’accueil n’est pas une preuve que des fichiers TEI externes, absents de ce dépôt, sont concédés sous CC0. Demander une confirmation explicitement rattachée aux fichiers, à la version, à l’indexation et à l’affichage d’extraits/textes complets. Aucun organisme n’a été contacté.

Une combinaison doit conserver les crédits de chaque producteur et respecter les conditions propres aux textes, métadonnées et images. La solution technique peut être simple sans que sa republication soit déjà validée. Aucun changement des textes ou des droits déclarés n’a été inféré automatiquement.

## 9. Combiner les sources : ce qui est raisonnable

### Rapprochements démontrés

- **Stanford ↔ ARTFL :** même ordre et contenu des 497 paragraphes ; identifiants de vues repris dans les `facs`. Association fiable dans le périmètre testé, mais pas de gain OCR justifiant de substituer le témoin ARTFL.
- **Stanford ↔ Persée :** sept correspondances retrouvées par titre, tome, page et contenu. Les identifiants Persée peuvent servir de références de contrôle. Mirecourt et Ferrières démontrent l’intérêt de distinguer l’œuvre documentaire, ses sections et ses témoins éditoriaux.
- Le METS fournit déjà des relations de catalogue qui évitent de devoir deviner tous les cahiers à partir des seuls « CAHIER » présents dans le XML Stanford. Cela aide à établir le registre ; cela ne délimite pas automatiquement chaque article dans le texte Stanford.

### Coûts et limites

Pas d’offsets partagés entre les sources. Des caractères, césures, omissions et regroupements de paragraphes diffèrent. Les notes peuvent être ailleurs ; deux cahiers peuvent partager une page. Un parent Persée peut recouvrir plusieurs divisions Stanford. L’alignement global par seul titre, seul numéro de page ou numérotation d’article serait insuffisant ; les numéros peuvent recommencer à chaque section.

Un assemblage mot par mot du « meilleur OCR » nécessiterait alignement, règles de conflit, validation sur scans et gestion de droits distincts, pour produire un nouveau témoin dont la provenance serait plus complexe. Le gain n’est pas démontré proportionné à ce coût. Il n’est pas recommandé maintenant.

En revanche, un **registre de correspondances limité**, sans réécriture des textes, est un effort raisonnable : identifiant interne, ID Persée de contrôle, plages de divisions Stanford, références de pages, statut et décision de validation. Avant une reprise automatisée des métadonnées Persée, obtenir les conditions applicables ; avant une extraction plus large, mesurer l’effort sur des cas simples et complexes. Aucun registre global n’a été construit pendant cette mission.

## 10. Gains démontrés, gains envisagés et recommandation

| Traitement actuel | Gain démontré | Ce qui reste à établir |
|---|---|---|
| Identifier les cahiers dans des divisions hétérogènes | Persée donne des IDs de cahiers, titres et hiérarchie METS ; regroupements contrôlés pour Mirecourt/Ferrières | Accord de reprise, couverture/qualité d’un registre plus large, correspondance complète des plages Stanford |
| Corriger les cinq anomalies ciblées | Persée corrige exactement quatre unités ; ARTFL aucune dans le service consulté | Qualité globale et absence d’omissions dans un éventuel export TEI |
| Reconstituer chaque article | Quelques séparations de paragraphes utiles chez Persée | Aucun extracteur d’articles générique fourni par les représentations examinées ; des paragraphes fusionnent ailleurs |
| Retrouver le scan et la référence | Les trois accès offrent une traçabilité de pages exploitable dans l’échantillon | Résolution des limites précises et vérification d’éditions/tirages pour l’ensemble |
| Disposer d’un corpus immuable hors ligne | Stanford répond déjà au besoin | Archive ARTFL corrigée avec version/licence ; export Persée documenté et autorisé |

Les trois choix demandés peuvent maintenant être départagés :

1. **Conserver Stanford : recommandé pour le texte de référence de la prochaine phase expérimentale**, grâce au snapshot reproductible, aux textes complets des passages contrôlés et à l’absence de gain lexical observé chez ARTFL. Cela ne résout ni les limites documentaires ni les droits numériques à clarifier avant publication.
2. **Remplacer principalement par ARTFL ou Persée : non justifié actuellement.** ARTFL ne corrige pas les paragraphes comparés ; Persée présente des améliorations locales mais aussi des erreurs et des omissions dans le HTML accessible. Un export TEI différent pourrait modifier cette conclusion, mais n’a pas été obtenu.
3. **Combiner : intéressant pour la documentation, différé pour une reprise automatisée/publication.** Utiliser Persée comme instrument de contrôle du catalogue est utile dès l’étude ; faire reposer le futur corpus sur ses métadonnées demande clarification des conditions et validation des correspondances. Pas de fusion OCR ni de substitution silencieuse.

La source « la plus facilement exploitable » dépend donc du niveau : Stanford pour conserver et extraire un témoin textuel versionné ; Persée pour identifier et décrire des cahiers. **Aucune transcription n’a été démontrée globalement la plus fidèle.**

## 11. Prochaine mission limitée proposée — non commencée

**Pilote de registre documentaire de 30 cahiers, sans application ni moteur de recherche.**

Prérequis : faire valider les demandes à adresser aux producteurs, obtenir les conditions applicables et, si possible, les exports ARTFL/Persée des sept cahiers déjà comparés. Refaire les cinq contrôles et les deux tests de complétude sur tout nouveau témoin avant de changer de source.

Périmètre proposé : les sept cahiers actuels puis 23 cas choisis explicitement dans les six premiers volumes, en incluant documents courts/longs, ordres différents, absence annoncée, sections multiples et annexes. Ne pas en faire un échantillon statistique représentatif par défaut.

Livrables de cette prochaine mission :

- Un registre parent → sections/passages sources, avec identifiants de témoins, plages XML, pages, métadonnées sourcées et décisions sur les annexes.
- Contrôle humain des débuts/fins et des cas incertains ; conservation exacte des textes choisis.
- Quelques articles d’essai par cahier validé, avec offsets et numérotation d’origine, sans découpage sémantique arbitraire.
- Mesure du temps de validation, du nombre de cas simples/complexes et des erreurs de frontière sur ces 30 cas ; estimation argumentée du travail restant, sans extrapolation d’exactitude à tout le corpus.

Critères de passage : chaque cahier admis a un parent vérifié, des bornes traçables, une référence au scan et un statut de droits documenté ; tout cas non résolu reste explicitement à l’écart. Aucun embedding, import PostgreSQL, changement de route ou déploiement n’est nécessaire à cette étape.

## 12. Fichiers, reproductibilité et vérifications

- [compare.py](compare.py) : analyse locale uniquement, sans réseau ni base.
- [cases.json](cases.json) : sélection explicite des cinq anomalies et références manuelles.
- [data/documents.json](data/documents.json) : appariement des sept cahiers, métadonnées, URLs des 27 fragments et images.
- [data/paragraph-pairs.json](data/paragraph-pairs.json), [data/probes.json](data/probes.json), [data/metrics.json](data/metrics.json) : mesures et contextes exacts (blancs réduits uniquement pour comparaison/présentation).
- [data/structure.json](data/structure.json), [data/coverage.json](data/coverage.json) : observations de structure et catalogue ARTFL.
- [data/access-log.json](data/access-log.json), [data/download-fingerprints.json](data/download-fingerprints.json) : tentatives, types de contenu et empreintes des téléchargements isolés. Les quelques premières récupérations par curl sont répertoriées séparément dans la provenance.
- [provenance.json](provenance.json) : portée, sources, limites et empreintes du premier audit avant/après.
- [verify.py](verify.py) : contrôle des résultats, des références et de l’intégrité du premier audit.

Reproduire l’analyse à partir du dossier de téléchargements, avec Python et `lxml` disponibles dans l’environnement d’audit :

```bash
python 1789/archives/1789-sources-comparison/compare.py \
  --downloads /tmp/cahier-1789-source-comparison \
  --output /tmp/comparaison-1789-reproduite

python 1789/archives/1789-sources-comparison/verify.py \
  --downloads /tmp/cahier-1789-source-comparison \
  --reproduced /tmp/comparaison-1789-reproduite
```

Les URLs et empreintes permettent de récupérer à nouveau les mêmes ressources publiques, sans garantir que les réponses externes seront inchangées. Ne pas envoyer de requêtes de masse ni tenter les exports réservés à partir de cette liste. Les images de contrôle restent temporaires ; elles sont référencées, pas incorporées au dépôt.

Vérifications : comparaison reproductible des résultats JSON ; cinq mesures de distances et deux contrôles de complétude ; intégrité des fichiers du premier audit ; Ruff sur les deux scripts ; liens locaux du rapport. Aucune suite applicative ni accès PostgreSQL n’a été nécessaire : seuls des fichiers de cette nouvelle étude ont été ajoutés, sans implémentation de la mission suivante.
