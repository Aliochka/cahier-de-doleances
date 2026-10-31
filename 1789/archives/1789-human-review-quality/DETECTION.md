# Erreurs humaines et contrôles disponibles

## Méthode

Les alertes sont **reconstruites sur les unités initiales**, sans décisions humaines, avec le code actuel inchangé. La partie historique « numéro absent/répété/suite irrégulière » est calculée séparément de l’extension. Les propositions OCR sont lues dans les sorties gelées de l’étude précédente : **aucun segmenteur n’est exécuté**.

Les deux signalements Codex `A:rt. 32.` et `i lfl` sont séparés des alertes automatiques. Le journal ne conserve pas l’écran exact affiché à chaque clic : on ne peut pas garantir que chaque alerte reconstruite était visible à ce moment précis.

Une alerte sur le numéro suivant n’est pas une alerte directe sur l’article fusionné. Une alerte due à une rubrique approximative peut aussi toucher un article réellement erroné par coïncidence : présence d’un signal ne prouve pas justesse du diagnostic.

## Résultats rétrospectifs

| Signal | Tous les 15 incidents | Dix incidents graves établis |
|---|---:|---:|
| Ancienne alerte directement sur la proposition affectée | 4/15 | 2/10 |
| Alerte directe avec l’extension, sans notes manuelles Codex | 9/15 | 7/10 |
| Marqueur proposé/suspect de l’extension, y compris dans les plages C | — | 8/10 |
| Alerte directe, marqueur ou changement de rôle visible dans le panneau | 12/15 | 8/10 |
| File élargie aux voisins des articles signalés + marqueurs C | — | 10/10 |

Ces rapports sont **des couvertures sur des erreurs connues**, majoritairement utilisées pour élaborer l’extension. Ce ne sont ni un rappel indépendant, ni une mesure de précision globale des contrôles. Le 10/10 de la file élargie est une observation de développement, pas une garantie future. Le contexte doit être réellement examiné : une alerte voisine ne corrige rien toute seule.

L’omission de l’article 6 du clergé d’Agen n’a pas d’article initial à signaler : elle est trouvée via un marqueur dans les passages non segmentés. Un tri limité aux articles existants ne peut pas mesurer ni garantir la complétude.

## Ce qui fonctionne et ce qui échappe encore

- Les six fusions d’Agen ont des propositions OCR précises. L’article 6 pris pour une rubrique est aussi repéré par une proposition et un changement de rôle.
- `56` à Mirecourt est correctement présenté comme **suspect**, sans conversion automatique en 5. La correction humaine confirme qu’une unité manquait à cet endroit.
- `A:rt. 32.` à Vic n’est **pas détecté par l’extension**. Le signalement du panneau provient d’un contrôle Codex. En revanche, la rupture du numéro suivant invite à examiner le voisin précédent.
- `4°\\Que…` dans la noblesse de Mirecourt reste sans signal direct. Un contexte de numérotation voisin déclenche une alerte, mais ne localise pas le début manqué. C’est un contre-exemple à la confiance dans la seule absence d’alerte directe.
- « De maintenir… » sans numéro visible ne peut pas être classé sûrement par une progression numérique. La décision humaine est conservée ; l’identité historique du numéro n’est pas démontrée par le TEI seul.
- Les rubriques et la prose de mandat absorbées sont visibles dans les différences de rôle/plage du panneau. Elles ne sont pas toutes transformées en avertissements sur les cartes.
- Terre-Franche n’est pas une fusion dans le corpus initial : son numéro absent est bien signalé. Le désaccord avec une réexécution brute du segmenteur doit rester un contrôle de régression distinct.

## Alertes sans erreur de découpage enregistrée

Dans le lot aléatoire, une seule proposition sur 108 porte une alerte de suite irrégulière : **16° après 14° dans le clergé d’Anjou**. L’utilisateur l’a acceptée sans correction. Le saut ne prouve pas qu’un article manque. C’est une alerte utile à examiner, mais un faux positif pour la tâche « trouver un découpage incorrect » selon la référence humaine disponible.

Sur les dix cahiers, 30 des 308 articles acceptés sans changement portaient une alerte de numérotation reconstruite. Plusieurs reprises à 1 ou numéros répétés sont légitimes ou dépendent de rubriques peu fiables. Ces 30 cas ne démontrent pas 30 erreurs de l’OCR ; ils montrent le coût d’un avertissement trop peu contextualisé.

## Charge du prétri existant

Sur les 719 articles initiaux : 79 signalés, 640 sans alerte directe, aucun parent bloqué dans ce lot déjà validé. Sur les **397 articles des 19 cahiers encore non examinés** :

- 40 portent une alerte directe automatique ;
- 357 n’en portent pas ;
- une file comprenant les articles signalés et leurs voisins immédiats couvre **69 articles distincts** ; il reste 328 articles hors de cette file.

Ce sont des **candidats de prétri**, pas des niveaux de fiabilité certifiés. Deux fusions graves connues figurent parmi les articles initialement sans alerte directe. Les contrôles actuels ne suffisent donc pas à autoriser sans évaluation la publication de toute la catégorie silencieuse.

Aucune nouvelle règle n’est développée ici. Les pistes à tester sont générales : contexte des ruptures numériques, prise en charge des délimiteurs OCR inattendus, conservation des contraintes humaines et contrôle des plages C. Elles sont justifiées par plusieurs marqueurs différents ou par le mécanisme général d’un début d’article absent de la liste des articles.
