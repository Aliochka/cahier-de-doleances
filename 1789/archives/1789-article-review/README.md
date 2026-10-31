# Vérification des articles de 1789

Le mode **Articles** est ajouté à l’interface locale existante. Le mode **Cahiers** garde ses routes, son journal et ses décisions. Aucun modèle de langage, service public, base, index ou embedding n’est utilisé ou modifié.

## Démarrer

Depuis la racine du dépôt :

```sh
/usr/bin/python3 1789/tools/document-review/server.py
```

Ouvrir **http://127.0.0.1:1789**, puis cliquer **Articles**. Si l’ancien serveur est encore lancé, l’arrêter avec Ctrl-C et le relancer ; recharger seulement le navigateur ne met pas à jour le Python déjà chargé. Le serveur écoute exclusivement sur `127.0.0.1`.

## État initial réel

| Objet | Nombre |
| --- | ---: |
| Cahiers aux limites validées humainement disponibles | 29 |
| Articles historiques proposés | 719 |
| Articles A, limites précédemment examinées par Codex | 217 |
| Articles B, propositions automatiques | 502 |
| Sections proposées | 4 |
| Passages techniques C | 793 |
| Articles/unité nouvellement validés humainement dans cette mission | **0** |

Digne reste hors du corpus puisque sa fin demeure incertaine dans le journal des cahiers. Aucun statut A/B/C n’est converti en validation humaine. Les tests utilisent des journaux synthétiques, distincts des deux journaux réels.

`data/initial-summary.json` conserve l’état initial ; `data/summary.json` et les exports locaux décrivent le dernier état exporté. Initialement, 723 unités (719 articles + 4 sections proposées) sont techniquement éligibles à une expérience d’indexation, avec leur statut explicite ; **aucune n’est déclarée prête à publier**. Ce choix ne signifie ni certitude documentaire ni autorisation de republication.

## Vérifier et valider rapidement

1. Choisir un cahier dans le mode Articles, renseigner le nom/pseudonyme du lecteur.
2. Lire les articles en continu : texte original, numéro attribué, rubrique, page, origine A/B et état de vérification. Les passages C sont accessibles avec « Afficher les passages techniques et le paratexte » ; leur texte complet reste consultable.
3. Pour une unité régulière, utiliser **Valider**. Une anomalie exige un examen individuel et une confirmation explicite.
4. Pour une suite régulière, ouvrir **Validation rapide par groupes**. Cocher les articles concernés, ou sélectionner explicitement une plage de rangs d’articles (par exemple 1–9 à Pierrelez). Ce rang de lecture n’est pas une numérotation historique inventée.
5. Relire les textes sélectionnés, cocher la confirmation et utiliser **Valider la sélection**. Le serveur refuse les groupes contenant des anomalies/incertitudes et les opérations de plus de 100 unités. Il n’existe pas de commande validant les 719 articles.
6. **Annuler la dernière décision** crée un nouvel événement : la décision antérieure reste historisée. Une validation groupée possède une trace pour chaque unité ; son annulation restaure tous les états antérieurs concernés.

Les cases cochées ne sont pas des validations. Les sélections sont réinitialisées lors d’un changement de cahier. Les passages C non classés ne peuvent pas être validés comme des articles par le bouton de groupe.

## Corriger sans modifier le texte

**Contexte / corriger** ouvre un seul éditeur partagé. Le cahier entier est affiché en lecture seule, avec l’unité courante surlignée. Choisir le texte à la souris ou au clavier, puis utiliser :

- **Utiliser la sélection entière**, ou définir séparément son début et sa fin ;
- **Séparer au début de la sélection**, pour deux articles fusionnés dans le même paragraphe ;
- **Fusionner les fragments sélectionnés**, après les avoir cochés ;
- **Ajouter un article manquant**, avec une plage explicite dans le texte conservé ;
- **Corriger le numéro attribué**, sans modifier le repère imprimé/OCR ;
- **Classer un passage ou une rubrique**, pour distinguer paratexte, passage revendicatif technique, section ou incertitude.

Prévisualiser, vérifier les unités remplacées et le texte résultant, puis confirmer. Toute modification de la sélection ou des champs invalide la prévisualisation précédente. Une correction ne peut pas absorber silencieusement un autre article ni un passage déjà classé/validé : utiliser une fusion explicitement sélectionnée ou ajuster les limites. Les restes, notes et blancs sont conservés dans des plages techniques.

Pour une rubrique prise à tort pour un article, utiliser **Classer…**, puis **Section historique** ou **Paratexte**. Classer un C comme passage revendicatif produit un passage technique de recherche, pas un article historique. L’ajout d’un article manquant est une opération distincte, explicitement humaine. Le numéro peut rester vide ; aucune renumérotation ou correction OCR n’est faite.

## Décisions, reprise et changement du parent

- Journal des cahiers, inchangé : `1789/data/private/document-review/decisions.jsonl`.
- Nouveau journal des unités : `1789/data/private/document-review/article-decisions.jsonl`.

Le second reprend le mécanisme existant de verrou, append-only, chaîne SHA-256, horodatage et contrôle de concurrence. Les décisions sont retrouvées au redémarrage. Les anciennes annotations ne sont jamais écrasées. Les journaux restent privés et ignorés par Git ; les sauvegarder séparément.

Une correction ou une incertitude du parent rend les unités incompatibles non éligibles et leurs validations périmées visibles. Après régénération du corpus, les décisions liées à une autre version de périmètre restent dans l’historique et doivent être réexaminées ; elles ne sont pas appliquées silencieusement aux nouvelles unités. [Format et règles détaillées](DATA.md).

## Export

Le bouton **Exporter les unités** écrit dans `1789/data/review-exports/`. Il ne télécharge rien et ne publie rien. En ligne de commande :

```sh
/usr/bin/python3 1789/archives/1789-article-review/export.py
/usr/bin/python3 1789/archives/1789-article-review/check.py
```

Les gros fichiers JSONL gzip sont exclus de Git ; les résumés, empreintes et scripts restent versionnables. Les unités conservent type, numéro attribué, texte original, positions, pages, version du parent, origine et décisions. Les champs d’éligibilité à l’indexation et de préparation à une éventuelle publication sont distincts. Aucun embedding n’est calculé.

## Vérifications réalisées et limites

[TESTS.md](TESTS.md) décrit les tests Python et navigateur. Pierrelez (9 articles), Ferrières (25 articles et rubriques), le clergé d’Alençon (nombreux B), la noblesse d’Agen (longs C) et des unités réparties sur plusieurs paragraphes sont couverts. Les tests incluent l’annulation de groupe, la reprise, les caractères Unicode et la mise en invalidité après modification du parent.

Les alertes de numérotation sont déterministes et indicatives : une reprise ou graphie atypique peut être légitime. Le logiciel assure la fidélité et la traçabilité, pas la vérité historique de la segmentation. Les corrections complexes restent à examiner dans le texte et, au besoin, la page numérisée.

L’annulation porte sur **la dernière décision du cahier**, pas une restauration arbitraire au milieu de corrections dépendantes. Les corrections travaillent sur des plages continues avec exclusion explicite des notes XML pour les articles/revendications ; une édition à colonnes intercalées peut nécessiter de rester incertaine. Les textes longs restent consultables intégralement ; l’interface nécessite JavaScript, les exports Python non.
