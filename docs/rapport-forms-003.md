# FORMS-003 — Formulaire et résultats réunis

Date : 20 octobre 2026. Implémentation et validation exclusivement sur Hal9000.

## Ajustements après revue

À la demande de l'utilisateur, les titres du questionnaire et des questions
sont désormais noirs. Chaque titre de question est directement cliquable et
mène à sa page individuelle ; le soulignement apparaît au survol ou au focus.
Le sommaire, les retours au sommaire et les liens de consultation répétés en
pied de section ont été supprimés. Les ancres stables `#question-{id}` restent
utilisables pour les liens directs et les anciennes URL Dashboard.
Deux grands liens présentés comme des boutons, en haut et en bas, permettent
également de « Voir les contributions à ce questionnaire ». Ils ouvrent
`/forms/{id}/contributions`, avec navigation précédente/suivante en HTML.
Cette entrée réutilise l'API historique de résolution par rang et l'affichage
public existant des contributions. Le rang de navigation reste distinct de
l'identifiant historique. Une lecture du rang suivant permet de reconnaître
la dernière contribution, l'API existante bornant les rangs hors plage.
Cette page de lecture effectue donc au plus deux appels de contribution ; le
chargement du détail Formulaire conserve son unique appel API. Aucun changement
backend ni nouvelle agrégation statistique n'est ajouté. La résolution historique
conserve son COUNT et son OFFSET : l'optimisation d'une navigation très profonde
ne fait pas partie de cet ajustement.

Validation après ces ajustements : **141 tests unitaires et 54 tests navigateur
réussis**, TypeScript et Biome réussis. Le parcours réel Formulaire → contribution
→ contribution suivante a également été vérifié avec JavaScript activé et
désactivé, à 320 px.

Les graphiques, détails et règles statistiques sont inchangés. Les descriptions
du sommaire ci-dessous retracent la livraison initiale, avant cette revue.

### Présentation des contributions après revue

Les cadres blancs des réponses sont retirés : la liste et les sections
réutilisent la présentation continue du Formulaire, avec séparations horizontales
et espacements. Le repérage des réponses ciblées par ancre est conservé.

Le titre de la contribution et les titres des questions réutilisent désormais
les styles noirs et la typographie du Formulaire. Les intitulés restent des
liens vers les pages Questions. Les doublons de présentation issus des imports
sont supprimés uniquement lorsque le texte entier reproduit les options,
les champs Autre, leur concaténation par lignes ou une valeur structurée.
Les textes complémentaires sont conservés intégralement. Aucune réponse en base
n'est modifiée et aucune ligne de réponse distincte n'est fusionnée.
Validation : 152 tests unitaires et 56 tests navigateur réussis ; le double
« Non » de la contribution du formulaire 4, rang 2, a été contrôlé sur les
données réelles avec et sans JavaScript.

## 1. Résultat

`/forms/{id}` présente désormais le questionnaire, son sommaire, toutes ses
questions et leurs résultats sur une page continue. Les graphiques HTML/CSS et
les tableaux sont rendus côté serveur ; JavaScript n'est pas nécessaire pour
consulter les résultats, utiliser les ancres ou ouvrir les détails.

Les sept questionnaires et leurs **120 questions** ont été contrôlés sur le
corpus local réel. L'ancienne URL Dashboard renvoie une **redirection HTTP 308**.
Un seul appel au contrat Formulaire enrichi suffit au chargement de chaque page.
Les requêtes de consultation utilisent toujours les instantanés FORMS-002 ;
aucune génération statistique n'a été lancée pour ce ticket.

Aucune migration, modification de données, reconstruction d'embeddings,
intervention sur Wallace, nouvelle dépendance graphique ou modification des
pages Questions et Enquêtes. Le serveur SSR local sur le port 3000 a été relancé
avec son environnement existant pour charger le nouveau build. FastAPI et le
modèle de recherche n'ont pas été redémarrés pour cette bascule frontend.

## 2. Structure définitive et choix UX

L'en-tête comporte le retour aux Enquêtes, le titre complet, le nombre de
questions et une indication sur la participation volontaire. Le libellé
« Questionnaire rapide » est affiché uniquement lorsque le nom source porte
explicitement la mention « questions rapides ». Aucune version détaillée ou
description éditoriale n'est déduite d'une métadonnée absente.

Le sommaire conserve tous les intitulés et l'ordre reçu. Deux colonnes sont
utilisées à partir de 48 rem, une seule sur petit écran, sans menu spécial ni
état client. Les liens natifs ciblent `#question-{id}` ; les identifiants BIGINT
restent des chaînes et ne passent jamais par une conversion numérique.

Chaque section contient son numéro, son intitulé intégral, le compteur de
réponses lorsqu'il est disponible, les résultats, les détails statistiques
éventuels, un accès à la page Question et un retour au sommaire. Des séparations
sobres remplacent les cartes administratives répétées. Les titres longs utilisent
une taille contenue et des retours à la ligne, sans troncature.

Les questions ouvertes affichent « Consulter les réponses à cette question ».
Le compteur est décrit comme un nombre de **réponses enregistrées**, sans
promettre autant de témoignages consultables : les critères des pages Questions
n'ont pas été modifiés.

Si `statistics_availability` est indisponible, un message général et des messages
locaux remplacent les graphiques. Les intitulés et liens documentaires restent
accessibles ; les compteurs indisponibles ne deviennent pas des zéros.

## 3. Visualisations retenues

| Situation | Présentation |
| --- | --- |
| Oui/Non complet, à choix unique | Barre proportionnelle à 100 %, accompagnée des deux libellés, effectifs et pourcentages |
| Répartition binaire incomplète, présence d'Autre ou compteurs incompatibles avec un total exhaustif | Barres indépendantes |
| Autres choix uniques | Barres horizontales dans l'ordre des modalités de l'API |
| Choix multiples | Barres indépendantes, mention « Plusieurs réponses possibles » et explication du total potentiellement supérieur à 100 % |
| Champ Autre | Modalité distincte, explicitement décrite comme pouvant accompagner une option |
| Aucun répondant | Message explicite et options à zéro conservées |
| Question ouverte | Compteur disponible et lien vers les réponses ; aucune statistique sémantique |

La représentation proportionnelle exige deux modalités Oui/Non, aucun Autre,
un dénominateur positif, et l'égalité entre somme des effectifs, sélections et
réponses. Elle s'appuie sur le type `single_choice` et les statistiques publiées
validées ; le frontend ne prétend pas recontrôler les réponses individuelles.
Les autres cas ne sont pas artificiellement ramenés à 100 %.

Les largeurs sont rapportées au dénominateur existant ; les pourcentages affichés
sont ceux du contrat, sans nouvel arrondi métier. L'ordre des catégories n'est
pas retrié. La palette associe bleu, vert pétrole, ocre, violet, terre cuite et
vert olive (`#203A8F`, `#176B68`, `#876400`, `#71539B`, `#A14F2B`, `#526D37`).
Les libellés et valeurs assurent la compréhension indépendamment des couleurs.

## 4. Détails et accessibilité

Les `<details>` natifs portent le libellé « Voir les détails statistiques »,
complété pour les technologies d'assistance par le numéro de la question.
Leur contenu comprend le tableau complet, les réponses enregistrées, contributions
distinctes, sélections d'options, champs Autre, total des sélections, dénominateur,
arrondis et explications. Date, méthode et génération publiées sont affichées.
La date utilise explicitement le fuseau Europe/Paris pour éviter un décalage
entre serveur et navigateur.

Les données essentielles restent hors des détails : intitulés, effectifs et
pourcentages des modalités sont du texte HTML. Les barres et pastilles sont
`aria-hidden`, afin d'éviter une seconde lecture de la même information. Les
tableaux possèdent une légende, des en-têtes et des associations `scope`.
Les titres, liens et sommaire utilisent une structure sémantique ; les sections
ciblées par ancre disposent d'une marge de défilement et peuvent recevoir le focus.

Les libellés et valeurs peuvent revenir à la ligne, y compris au zoom texte
200 %. Une feuille d'impression rend les détails lisibles sans devoir ouvrir
manuellement les accordéons. Les couleurs forcées sont prises en compte.
Le contraste des six couleurs est vérifié par test contre le fond clair utilisé
(ratio supérieur à 4,5:1) ; les données ne reposent jamais sur ce seul contraste.

**Vérification partielle avec Orca réel :** un essai isolé avec Xvfb, D-Bus et
Speech Dispatcher a été réalisé sans changer la configuration du poste.
Après avoir imposé X11 au navigateur, Orca a reconnu le titre, la structure
(14 titres pour le formulaire 2), l'intitulé de la première question et
« Voir les détails statistiques — question 1 toggle button expanded » après
activation au clavier. Ces annonces sont consignées dans
`/tmp/forms003-orca/announcements.txt`. Le périphérique de sortie audio de cette
session isolée n'a pas fonctionné ; il s'agit d'une inspection des annonces
produites par Orca, sans écoute humaine ni parcours complet des données.
La validation complète avec lecteur d'écran reste à réaliser. Les vérifications
sémantiques, clavier et automatisées ne constituent pas une certification RGAA.

## 5. Architecture et composants

Créés :

- `frontend/app/features/forms/form-questions.tsx` : sommaire et sections.
- `frontend/app/features/forms/result-charts.tsx` : barres, conditions Oui/Non et détails.
- `frontend/app/features/forms/results.module.css` : mise en page, mobile, impression.
- `frontend/app/features/forms/form-results.test.tsx` : tests des présentations et cas statistiques.
- `frontend/tests/smoke-forms-local.mjs` : recette réelle, bornée et en lecture seule.

Modifiés :

- `frontend/app/routes/form.tsx` : utilise directement `FormDetail` enrichi.
- `frontend/app/routes/dashboard.tsx` : loader de redirection uniquement.
- Client API : suppression de l'appel frontend `getFormStats` devenu inutile.
- Fixtures, tests de navigation et ancienne suite Dashboard adaptés à la page fusionnée.
- README frontend et guide des statistiques locales.

Supprimé : `frontend/app/features/surveys/question-list.tsx`, remplacé par la
présentation continue. Les tests qui reproduisaient l'ancien Dashboard sont
remplacés par les tests du nouveau contrat d'affichage et de la redirection.

Les composants `Statistics` et Recharts des pages Questions sont conservés.
Ces pages ne sont pas modifiées. Les contrats statistiques backend restent
accessibles ; aucune suppression d'endpoint n'est nécessaire à cette fusion.
OpenAPI et les types générés restent ceux, vérifiés, de FORMS-002. Aucun paquet
n'a été ajouté ou retiré.

Le loader Formulaire transmet toujours le signal d'annulation, conserve les
statuts d'erreur et `Cache-Control: private, no-store`. Le chargement effectue
un seul GET `/api/v1/forms/{id}`. Ouvrir les détails ou le sommaire ne provoque
ni appel API ni recalcul. Les réponses citoyennes individuelles ne sont pas chargées.

## 6. Anciennes URL et compatibilité

`/forms/{id}/dashboard` renvoie côté serveur :

```http
HTTP/1.1 308 Permanent Redirect
Location: /forms/{id}
```

Aucun appel statistique ou documentaire n'est exécuté avant cette redirection.
Les paramètres de requête sont conservés. Le fragment n'est pas transmis au
serveur : le navigateur le conserve en suivant la redirection, ce qui a été
vérifié avec et sans JavaScript pour `#question-{id}`. Le formulaire cible ne
redirige pas vers Dashboard : aucune boucle. Les liens internes vers le Dashboard
ont disparu.

Le comportement existant de rejet des anciens paramètres `contrib` sur Formulaire
reste conservé ; la redirection ne réinterprète pas ces paramètres. Les identifiants
inexistants aboutissent à la réponse documentaire habituelle de la destination.

## 7. Tests et recette réelle

| Vérification | Résultat |
| --- | --- |
| Vitest | **134 tests réussis**, 16 fichiers |
| Playwright, suite frontend complète | **52 tests réussis** |
| Vérifications de build sans réseau | **6 tests réussis** |
| Biome | Réussi |
| TypeScript / types des routes | Réussi |
| Build normal et build de tests | Réussis |
| Export OpenAPI et types générés, mode vérification | Réussis |
| `git diff --check` | Réussi |

Les tests couvrent le SSR, les BIGINT, l'ordre, les deux types de barres, les
choix multiples totalisant 170 %, Autre associé à une option, options à zéro,
absence réelle de réponses, statistiques indisponibles, détails natifs, liens,
ancres, redirection sans API, lecture sans JavaScript et non-régression des
navigations Questions/Enquêtes. Les états synthétiques évitent toute altération
du corpus réel. Les tests backend de calcul ne sont pas réexécutés pour cette
modification exclusivement frontend ; les résultats FORMS-002 restent documentés
dans leur propre rapport.

La recette réelle démarre un serveur SSR temporaire contre FastAPI existant,
puis le ferme. Avec JavaScript, les sept formulaires sont parcourus :

| Formulaire | Questions | Graphiques |
| --- | ---: | ---: |
| 2 | 12 | 12 |
| 4 | 33 | 8 |
| 5 | 37 | 7 |
| 7 | 8 | 1 |
| 10 | 16 | 6 |
| 11 | 7 | 7 |
| 12 | 7 | 7 |
| Total | **120** | **48** |

Sans JavaScript, les formulaires 2 et 5 ont également été contrôlés, avec ouverture
des détails, ancres, ancienne URL, accès à une page Question et retour. Les 37
questions du formulaire 5 sont présentes dès la réponse HTML. Aucun module
`stats-chart` n'est demandé pendant la consultation des Formulaires. La génération
statistique publiée n'est pas recalculée ni modifiée.

Les tests navigateur contrôlent le clavier, les intitulés longs, 320 px, le texte
à 200 %, les couleurs forcées et l'impression. Un contrôle complémentaire sur le
serveur local relancé, avec les effectifs réels à 320 px et texte 200 %, confirme
l'absence de débordement horizontal. Il s'agit du zoom texte, pas d'une campagne
multinavigateur de tous les modes de zoom.

Captures inspectées : `/tmp/forms-003-real-desktop.png`,
`/tmp/forms-003-real-mobile.png`, `/tmp/forms-003-real-zoom.png`.
Le PDF `/tmp/forms-003-print.pdf` contient les tableaux et méthodes des détails
fermés dans la page écran. Ces artefacts temporaires ne sont pas des livrables
versionnés.

## 8. Performances observées

Mesures ponctuelles sur Hal9000, sans campagne de charge. L'instrumentation
sépare le GET API complet du traitement SSR restant, puis mesure le navigateur.
« SSR hors API » est une différence de temps muraux, incluant validation et
sérialisation ; ce n'est pas une mesure CPU isolée de React. PostgreSQL n'a pas
été réinstrumenté : le budget constant des lectures précalculées est celui de
FORMS-002.

| Formulaire | API HTTP (ms) | SSR hors API (ms) | Total serveur SSR (ms) | HTML brut (octets) |
| --- | ---: | ---: | ---: | ---: |
| 2 | 4,36 | 33,23 | 37,60 | 66 903 |
| 4 | 4,05 | 17,21 | 21,26 | 77 478 |
| 5 | 3,25 | 15,18 | 18,42 | 77 686 |
| 7 | 2,93 | 5,10 | 8,03 | 24 803 |
| 10 | 2,49 | 10,27 | 12,76 | 54 675 |
| 11 | 2,96 | 8,58 | 11,54 | 41 448 |
| 12 | 2,44 | 8,49 | 10,93 | 45 051 |

Le premier formulaire inclut l'échauffement du processus SSR. Les retours sur les
formulaires 2 et 5 donnent environ 12,3–12,9 ms hors API. Les corps JSON sont
inchangés par cette implémentation : par exemple 11 498 octets pour le formulaire
2 et 16 485 pour le formulaire 5.

Comparaison avec les audits précédents : l'ancien endpoint statistique du
formulaire 2 coûtait environ **3 664 ms** dans FORMS-001. FORMS-002 a déjà supprimé
ce coût par le précalcul (12,6 ms lors de son contrôle ASGI). FORMS-003 conserve
ce gain et évite le second parcours Formulaire → Dashboard. Ces mesures ne sont
pas toutes prises avec le même protocole : la comparaison indique l'ordre de
grandeur, pas un facteur d'accélération rigoureusement établi.

La page continue est volontairement plus riche en HTML. Pour le formulaire 5,
l'audit initial relevait environ 35,9 ko pour Formulaire et 28,0 ko pour Dashboard
sur deux pages séparées ; la nouvelle page unique atteint 77,7 ko, avec sommaire,
37 sections et tous les détails. La compression gzip calculée sur cette réponse
est de 13,4 ko ; elle est indicative, le serveur temporaire mesure les transferts
sans cette compression.

Côté navigateur local, le premier chargement réel du formulaire 2 a pris environ
108 ms jusqu'à la fin de navigation, dont 39 ms d'exécution JavaScript et 8,5 ms
de layout. Les autres formulaires ont pris environ 41–62 ms, avec 6,5–10,7 ms de
scripts. Sans JavaScript, les formulaires 2 et 5 ont chargé en environ 44 et 40 ms.
Ce ne sont ni des mesures d'expérience sur réseau distant ni des garanties publiques.

Le module de route Formulaire pèse environ **9,52 ko** avant compression
(**3,30 ko gzip**), sa feuille CSS environ **5,04 ko** (**1,51 ko gzip**).
Les graphiques n'ajoutent aucun JavaScript de bibliothèque. Le module Recharts
existant reste produit pour les Questions (environ 374 ko, 108 ko gzip), mais
n'est pas téléchargé sur Formulaire. React et les ressources communes restent
chargés lorsque JavaScript est activé : la page n'est pas une page sans scripts.

Résultats détaillés de la recette : `/tmp/forms-003-local-results.json`.
Les mesures précèdent un dernier ajustement CSS permettant le retour à la ligne
des grands effectifs au zoom ; ce changement n'a pas modifié la structure des
réponses ou le parcours API. Le build et le contrôle réel mobile ont été repris.

## 9. Reproduction et limites restantes

Avec FastAPI déjà lancé sur `127.0.0.1:8000` et les statistiques publiées :

```bash
pnpm --dir frontend check
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend test:e2e
pnpm --dir frontend build:offline
pnpm --dir frontend test:build
pnpm --dir frontend exec node tests/smoke-forms-local.mjs
```

La dernière commande utilise temporairement le port 4187. Elle n'écrit aucune
fixture en base, ne génère aucune statistique et n'utilise pas le modèle BGE-M3.
Pour la consultation courante, garder le lancement SSR habituel du
[guide local](search-local.md) ; après reconstruction, redémarrer le serveur qui
avait déjà importé l'ancien build.

Restent à réaliser : parcours complet avec écoute et lecteur d'écran réel, vérifications sur d'autres
navigateurs et dispositifs physiques, et éventuelle recette d'accessibilité plus
large. Les conditions de représentation Oui/Non doivent être réexaminées si un
futur import change les garanties de choix unique. Les longs sommaires restent
volontairement simples : aucune virtualisation, recherche secondaire ou navigation
complexe n'a été ajoutée.

FORMS-003 est terminé. Aucun travail d'exploration, recherche filtrée, refonte des
Questions ou modification supplémentaire du stockage statistique n'est engagé.
