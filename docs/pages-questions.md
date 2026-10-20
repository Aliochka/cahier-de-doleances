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
lorsque son compteur publié vaut zéro. Les réponses ouvertes conservent leur
lecture et leur filtre historique ; aucune recherche hybride filtrée n'est ajoutée.

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
