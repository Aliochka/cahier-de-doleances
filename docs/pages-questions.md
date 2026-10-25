# Harmonisation des pages Questions

20 octobre 2026, Hal9000 uniquement.

Les pages Questions reprennent la présentation des Formulaires : titre noir,
graphiques HTML/CSS immédiatement visibles, palette commune, libellés, effectifs
et pourcentages accessibles sans interaction. La répartition Oui/Non complète
utilise une barre proportionnelle ; les autres choix utilisent des barres
indépendantes. Les pourcentages ne sont jamais renormalisés.

Les tableaux, effectifs détaillés et définitions sont regroupés dans les détails
natifs « Voir les détails statistiques ». Les données et graphiques sont présents
dans le HTML SSR, sans chargement de Recharts. Les métadonnées de génération ne
sont pas inventées : l'endpoint statistique Question ne les fournit pas.

Sous les résultats, les questions comportant des champs Autre présentent
« Réponses « Autre » à la question », avec les textes citoyens, auteurs publics,
liens ancrés vers les contributions et pagination. Aucun champ Autre n'est lu
lorsque son compteur publié vaut zéro. Les réponses ouvertes conservent leur lecture et leur filtre historique dans
l’onglet « Réponse à la question ».

## Adaptation minimale de l'API

Le paramètre optionnel `other_only=true` de l'endpoint existant `/answers`
filtre les champs Autre structurés et produit leur texte public en une lecture
SQL, sans requête supplémentaire par réponse. Seuls les éléments de type chaîne
non vides sont retenus ; plusieurs textes de la même réponse sont séparés par
deux sauts de ligne. Les options sélectionnées ne sont pas recopiées.
Le mode n'est accepté que pour les questions à choix. Sans ce paramètre,
le comportement antérieur est conservé. OpenAPI et les types ont été actualisés.

La pagination conserve le classement historique par date et identifiant, son
curseur et ses liens HTML. Les statistiques restent les instantanés publiés ;
aucun calcul statistique, migration, modification du corpus ou des embeddings.
Le filtre JSONB peut devoir lire plusieurs candidats pour constituer un lot ;
le timeout SQL existant de cinq secondes reste actif, sans nouvel index dans
cet ajustement. Les erreurs partielles conservent leur statut HTTP et les
informations documentaires disponibles.

## Validation

- 104 tests backend réussis sur les bases isolées `_test`, dont filtrage Autre,
  provenance, anonymat, textes multiples, texte importé absent et pagination.
- 153 tests unitaires frontend réussis.
- 56 tests navigateur réussis, avec SSR, détails au clavier, pagination,
  parcours sans JavaScript, mobile et zoom.
- TypeScript, Biome, Ruff, export OpenAPI et vérification des types réussis.
- Corpus réel : question 8 (Oui/Non) et question 159 (choix multiples et Autre),
  avec JavaScript activé puis désactivé ; détails, liens et pagination vérifiés.
- Aucun module Recharts demandé pendant cette recette. Capture inspectée :
  `/tmp/questions-redesign-mobile.png`.
- Recherche hybride vérifiée après redémarrage : HTTP 200 sur une recherche réelle.

FastAPI et le serveur SSR local ont été relancés avec leur environnement existant.
Aucun déploiement sur Wallace. La vérification avec lecteur d'écran complet
reste à conduire ; la validation automatisée ne constitue pas une certification.

## Recherche dans les réponses

L’onglet « Rechercher dans les réponses », placé à droite du premier, utilise
le moteur lexical H1 existant avec `question_id`, sans BGE-M3, recherche vectorielle
ni fusion RRF. L’URL de la question porte
`tab=search`, puis `q` et le curseur ; les liens et le formulaire GET fonctionnent
aussi sans JavaScript. Les onglets, champs, boutons, alertes et textes citoyens
réutilisent le design system. Les statistiques restent dans le premier panneau.

Pour les questions à choix, seuls les textes libres « Autre » sont recherchables.
Si leur compteur publié est nul, un message l’explique sans appeler le moteur.
Une panne des statistiques est affichée comme une erreur réessayable. Une saisie
vide n’appelle pas le moteur. Les résultats restent une sélection par pertinence,
sans total exhaustif ; changer la saisie réinitialise la pagination. Les pages
de recherche sont `noindex, follow` et ont la page question comme canonique.

Le contrat et l’index SQL requis sur la base de recherche sont décrits dans
[api-search.md](api-search.md). Cet index est additif : aucune reconstruction du
corpus ni des embeddings n’est nécessaire.

Mesures historiques avant la bascule lexicale : recherche réelle sur les questions 159 et 158 (50 résultats
chacune en environ 3,5 s et 4,1 s après installation de l’index), et recherche
générale en environ 0,7 s sur la même machine. Ces mesures ne sont pas une
garantie de latence sur une autre installation.

Le compte rendu actuel de la bascule, ses tests et les mesures SQL bornées sont
dans [recherche-lexicale-par-question.md](recherche-lexicale-par-question.md).
