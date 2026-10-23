# RAG-027 P4 — Dominance de la couverture complète dans le domaine OR-A

23 octobre 2026. Audit et démonstration uniquement. Aucun accès à Wallace, aucune requête PostgreSQL, aucune modification du moteur, du corpus, des index ou des paramètres. Les seules vérifications exécutées sont des calculs arithmétiques locaux. Ce document complète le [rapport P4 général](rag027-p4-optimisations-exactes.md).

## 1. Conclusion et portée

**Oui, la dominance stricte est démontrable pour le domaine OR-A de H1, avec ses 1 à 32 lexèmes, sous les préconditions précisées ci-dessous.** Pour 2 à 32 lexèmes, même en conservant les arrondis float4/float8, la différence entre le score de n’importe quel document complet et celui de n’importe quel document incomplet est **strictement supérieure à 0,00331438**. Pour un lexème, aucun document incomplet n’est admissible : la propriété est triviale.

Par conséquent, **si au moins 50 documents admissibles couvrent tous les lexèmes, le véritable top-50 H1 appartient entièrement à ce sous-ensemble**. Il faut toujours calculer son véritable classement avec le score, les casts et le départage H1 originaux. Le certificat numérique par requête proposé dans P4 devient superflu dans ce domaine vérifié.

La preuve candidate en nombres réels donne la bonne intuition, mais **sa borne basse n’est pas littéralement valable pour les scores flottants** : un exemple à cinq lexèmes la manque d’environ 4 × 10⁻⁹. Cela ne réfute pas la dominance ; la marge entre complets et incomplets reste beaucoup plus grande.

La conclusion ne vaut pas pour des vecteurs quelconques. Des contre-exemples existent avec des entrées sans positions ou des positions uniquement de poids D. L’importeur inspecté produit des positions de poids A ; cela ne constitue pas, à lui seul, une vérification exhaustive de l’historique du corpus installé.

**Première expérience recommandée, après autorisation :** mesurer la cardinalité et le vrai top-50 du sous-ensemble complet de `democratie-02`, en gardant intégralement le scoring natif. Le gain dépend encore de sa sélectivité et du plan retenu ; aucun facteur d’accélération n’est établi.

## 2. Contrat exact examiné

Révision locale examinée : `04f7a184d722f80b29b29f89872414db9831283b`. La référence historique H1 reste `0eebaecbd0f14bc88ae12d85cc6fba35d0fd5a73` ; la preuve porte sur les expressions actuellement présentes et identifiées ci-dessous, pas sur une assimilation des deux révisions.

| Élément | Référence locale | Conséquence |
|---|---|---|
| IDF et total | [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L23–58 | IDF de chaque lexème et total commun à tous les documents de la requête. |
| Arbre arithmétique | [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L62–73 | Sommes des CASE, multiplication puis division ; rang float4 élargi en float8 ; additions dans l’ordre original. |
| Coefficients | [search/flexible.py](../rag/src/cahier_rag/search/flexible.py), L19 | 0,5 / 0,3 / 0,2. |
| Admissibilité et tri | [tuning/lexical.py](../rag/src/cahier_rag/tuning/lexical.py), L100–103 | Filtres originaux, Q, `score DESC, document_id COLLATE "C"`, limite 50. |
| Normalisation | [search/preparation.py](../rag/src/cahier_rag/search/preparation.py), L89–125 | Lexèmes uniques ; plafond 32 ; phrases et exclusions peuvent sortir du domaine OR pur. |
| Construction des vecteurs | [fullcorpus/store.py](../rag/src/cahier_rag/fullcorpus/store.py), L120–126 | `setweight(to_tsvector('pg_catalog.french', ...), 'A')`. |
| Fusion | [search/hybrid/core.py](../rag/src/cahier_rag/search/hybrid/core.py), L37–62 | Conserver la liste lexicale ordonnée conserve sa contribution RRF, à liste vectorielle fixée. |

Préconditions de la spécialisation démontrée :

1. Q est exactement une disjonction de `m` lexèmes positifs **uniques**, sans préfixe, restriction de poids, phrase, NOT ou autre opérateur ; `1 ≤ m ≤ 32`. Les termes des couvertures sont exactement ceux de Q.
2. Les vecteurs sont valides. Chaque lexème recherché présent possède au moins une position stockée ; toutes ses positions stockées sont de poids A. Les lexèmes étrangers à Q n’interviennent pas dans cette condition.
3. Appel `ts_rank_cd(vector, Q, 32)` à poids par défaut ; formule et types H1 inchangés, sans préfiltrage approximatif.
4. IDF finies non négatives, total strictement positif, issu des mêmes IDF ; pas de NULL, NaN, débordement ou sous-débordement. « IDF non négatives » seul ne suffit pas si elles sont toutes nulles : la division serait indéfinie.
5. Calculs float8/float4 usuels IEEE 754, arrondi au plus proche, égalités départagées au pair ; mêmes paramètres et même état logique du corpus pour toutes les étapes.

Avec les statistiques valides H1 (`0 ≤ df ≤ N`, `N = 5 172 356`), les IDF sont positives et d’ordre 10⁻⁷ à 17 : aucune difficulté de plage flottante n’intervient. Les filtres documentaires ordinaires peuvent restreindre l’ensemble sans affaiblir la preuve.

Le texte libre des deux questions lentes emprunte le chemin OR en l’absence de phrases/exclusions. Les lexèmes, leur nombre et les IDF effectifs restent à relever depuis la normalisation réelle ; ils ne sont pas devinés ici.

## 3. Réduction exacte du rang PostgreSQL 17.11

Source amont examinée : [tsrank.c, étiquette REL_17_11](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/tsrank.c). Il faudra confirmer la correspondance avec le paquet de Wallace avant validation native.

Les points de code déterminants sont `get_docrep` (L727–846), `Cover` (L645–724), `calc_rank_cd` (L850–949) et `ts_rankcd_ttf` (L986–997). Les entrées sans positions sont ignorées. Les occurrences sont ordonnées ; le regroupement exige la même entrée lexicale et la même position pondérée. Le rang est accumulé en double, normalisé, puis retourné en float4.

La déduction suivante est propre au domaine OR-A :

- Une occurrence de n’importe quel opérande suffit à satisfaire Q. La recherche avant/arrière d’une couverture s’arrête donc sur **une seule entrée** de la représentation, et avance ensuite à l’entrée suivante.
- Pour cette couverture : `begin = end`, `p = q`, poids inverse A = 1, `Cpos = 1`, `nNoise = 0`. Sa contribution est exactement 1.
- Soit **K le nombre total de positions stockées des lexèmes recherchés**, comptées séparément par lexème. L’accumulation donne exactement l’entier K. La seule normalisation active donne K/(K+1), puis intervient l’arrondi float4.

En notant RN64 et RN32 les arrondis aux formats correspondants, le rang élargi utilisé par H1 est donc exactement :

```text
R(K) = float8(RN32(RN64(K / (K + 1))))
```

K et K+1 sont représentables exactement dans la plage considérée. L’élargissement float4 → float8 ne rétablit pas les bits perdus. Les conversions sont explicites dans [float.c, `ftod` et `dtof`](https://github.com/postgres/postgres/blob/REL_17_11/src/backend/utils/adt/float.c#L1115-L1142) ; les opérations natives float8 sont dans [float.h](https://github.com/postgres/postgres/blob/REL_17_11/src/include/utils/float.h#L146-L235).

### Positions communes, saturation et doublons

| Cas | Effet sur la preuve |
|---|---|
| Deux lexèmes différents à la même position | Deux entrées distinctes contribuent chacune 1. K n’est **pas** le nombre de positions distinctes dans le document. |
| Plusieurs lexèmes à la position saturée 16 383 | Même conclusion. `Cover` réinitialise p et q à chaque appel ; une position égale à celle de la couverture précédente n’est pas supprimée. |
| Occurrences originales fusionnées/tronquées lors de la construction | Seules les positions conservées comptent. On ne retrouve pas le nombre d’occurrences du texte initial. |
| Entrée sans positions | Peut satisfaire le `@@` simple, mais ne contribue pas au rang ; K ≥ m n’est plus garanti. |
| Plusieurs occurrences du même lexème | Contribuent selon ses positions stockées ; elles ne créent pas de nouveaux termes de couverture. |
| Répétitions dans la question brute | La normalisation H1 déduplique les lexèmes. m se mesure après cette étape. |
| Répétition d’un opérande dans un tsquery construit autrement | Ne pas compter deux fois ce lexème dans m : la représentation peut regrouper ces opérandes. Hors de la garde actuelle tant que non canonisé. |

Les limites de stockage sont 256 positions par lexème et une position maximale de 16 383 : [limites PostgreSQL 17](https://www.postgresql.org/docs/17/textsearch-limitations.html), [ts_type.h, L82–93](https://github.com/postgres/postgres/blob/REL_17_11/src/include/tsearch/ts_type.h#L82-L93). Ainsi :

```text
document complet   : m ≤ K ≤ 256m ≤ 8192
document incomplet : 0 ≤ K ≤ 256(m−1)
```

`length(tsvector)` compte les lexèmes, pas K ; ce contrôle P3 ne peut pas remplacer le rang.

## 4. Bornes candidates et preuve flottante

### 4.1 Arithmétique réelle : intuition correcte

Sans arrondis, un document complet a ses deux couvertures maximales, et K ≥ m :

```text
S_complet ≥ 0,8 + 0,2 × m/(m+1)
S_incomplet ≤ 0,5 + 0,3 × (m−1)/m + 0,2 = 1 − 0,3/m
écart ≥ 0,3/m − 0,2/(m+1) = (m+3)/(10m(m+1)) > 0
```

La majoration néglige volontairement la perte d’IDF. Elle reste valable même si le lexème manquant a une IDF nulle, pourvu que le total soit positif.

### 4.2 La borne basse littérale est fausse après arrondi

Pour m = 5, une position A par lexème et une couverture IDF calculée à 0,5 :

```text
rang float4 élargi : 0,8333333134651184
score H1          : 0,9666666626930237
borne réelle      : 29/30 ≈ 0,9666666666666667
écart             : −3,973642962821581 × 10⁻⁹
```

Ce cas est compatible avec des IDF valides égales et des sommes calculées dans le même ordre. **C’est un contre-exemple à la borne réelle utilisée telle quelle, pas à la dominance.** Il provient surtout de l’arrondi float4, que le cast float8 conserve.

Pour la borne haute, substituer simplement un rang flottant égal à 1 peut aussi dépasser légèrement la valeur réelle : à m = 2, la majoration opérationnelle vaut `0,8500000000000001`, contre 0,85. Ce n’est pas un contre-exemple documentaire : un tel rang 1 est inaccessible dans le domaine OR-A borné. Avec K ≤ 256(m−1), le rang maximal reste au plus `0,9998739957809448` pour m ≤ 32. La réserve sur sa contribution dépasse 2,52 × 10⁻⁵, bien au-delà des erreurs float8 des couvertures (< 10⁻¹⁴ ici). La borne réelle haute reste donc conservative **dans ce domaine borné**, mais pas par la seule substitution naïve « rang ≤ 1 » dans une expression réelle.

### 4.3 Preuve conservant l’ordre des opérations H1

Notons `c₃` et `c₂` les valeurs binaires float8 effectivement liées pour 0,3 et 0,2. Pour un document d, posons :

```text
L(d) = somme gauche-associative float8 des CASE IDF originaux
A(d) = RN64(RN64(0,5 × L(d)) / total_idf)
b_j  = RN64(RN64(c₃ × float8(j)) / float8(m))
c(K) = RN64(c₂ × R(K))
F(a,b,c) = RN64(RN64(a+b) + c)
S(d) = F(A(d), b_nombre_de_termes_présents, c(K(d)))
```

On ne remplace pas A(d) par un quotient réassocié, ni la somme finale par `0,8 + ...`.

Soit A* la composante IDF commune à tous les documents complets. Toutes les opérations originales sont monotones sur ces valeurs non négatives, avec le même total positif. En remplaçant certains CASE positifs par zéro, on obtient donc **A(incomplet) ≤ A***, arrondis compris. Cette observation évite de faire dépendre la dominance de l’égalité binaire A* = 0,5.

De plus, **0 ≤ A* ≤ 1** est une borne très large garantie pour les IDF H1 valides. Pour au plus 32 termes normaux, l’erreur relative d’une somme positive est bornée par `γ₃₁ = 31u/(1−31u)`, avec `u = 2⁻⁵³`. Même en autorisant des ordres de sommation différents au numérateur et au total :

```text
A* ≤ 0,5 × (1+γ₃₁)/(1−γ₃₁) × (1+u)²
   < 0,5 + 3,56 × 10⁻¹⁵ < 1
```

Le total est bien une somme float8 : [pg_aggregate.dat, `sum(float8)`](https://github.com/postgres/postgres/blob/REL_17_11/src/include/catalog/pg_aggregate.dat#L69-L70). L’argument ne suppose pas une réassociation de son calcul avec celui des CASE.

Par monotonie, pour tout complet x et tout incomplet y :

```text
S(x) ≥ F(A*, b_m, c(m))
S(y) ≤ F(A*, b_(m−1), c₂)
```

Les deux additions successives de F portent sur des valeurs inférieures à 2. Chacune a une erreur absolue au plus 2⁻⁵³. La comparaison des deux expressions consomme donc au plus 4 × 2⁻⁵³ = 2⁻⁵¹. Il suffit de vérifier :

```text
g_m = (b_m − b_(m−1)) + (c(m) − c₂) − 2⁻⁵¹ > 0
```

Dans cette dernière ligne, les soustractions servent à la **preuve en rationnels exacts des valeurs binaires**, et ne proposent pas une nouvelle expression SQL.

Les 31 cas m = 2 à 32 ont été évalués localement par arrondi explicite au plus proche/pair en précision 53 puis 24 bits, avec soustractions en rationnels exacts. Les conversions de rang ont aussi été recoupées avec la conversion float32 locale.

| m | R(m) | Borne basse opérationnelle si A* = 0,5 | Borne haute opérationnelle si A* = 0,5 | g_m, affichage approché |
|---:|---:|---:|---:|---:|
| 2 | 0,6666666865348816 | 0,9333333373069763 | 0,8500000000000001 | 0,08333333730697587 |
| 5 | 0,8333333134651184 | 0,9666666626930237 | 0,94 | 0,02666666269302323 |
| 16 | 0,9411764740943909 | 0,9882352948188782 | 0,98125 | 0,006985294818877719 |
| 32 | 0,9696969985961914 | 0,9939393997192383 | 0,9906249999999999 | 0,0033143997192378594 |

Le minimum exact des g_m calculés est, pour m = 32 :

```text
29853458681033 / 9007199254740992 > 0,00331438
```

Ainsi S(x) > S(y), avec une marge strictement positive, sans hypothèse sur la répartition des IDF au-delà des conditions annoncées. Les colonnes utilisant A* = 0,5 sont des illustrations ; la preuve de marge vaut pour tout A* dans [0,1].

La démonstration en réels s’écrit pour tout m. La vérification flottante présentée ici est volontairement limitée aux valeurs admises par H1 ; elle ne constitue pas une preuve pour un m arbitrairement grand. Ce sont des vérifications arithmétiques locales, **pas une exécution des fonctions PostgreSQL installées**.

## 5. Contre-exemples et limites du domaine

Deux exemples synthétiques montrent pourquoi les invariants de vecteurs sont nécessaires. Prenons Q = `'a' | 'b'`, N = 1000, df(a) = 2 et df(b) = 999. Ces statistiques sont réalisables : une intersection d’un document, un autre document contenant seulement a, et 998 contenant seulement b.

La formule IDF H1 donne environ `w_a = 5,992464047441065` et `w_b = 0,0014996253747658356`. Les scores ci-dessous ont été calculés localement avec les étapes flottantes du modèle, sans créer de données PostgreSQL.

| Vecteurs comparés | Score complet | Score incomplet | Conclusion |
|---|---:|---:|---|
| Complet : `'a' 'b'`, entrées sans positions ; incomplet : 256 positions A de a | 0,8 | 0,8490966952036305 | La présence lexicale seule ne garantit pas la dominance. |
| Complet : une position D de a et une de b ; incomplet : 256 positions D de a | 0,8333333343267442 | 0,8423561132143422 | Des positions disponibles, mais de poids D, ne suffisent pas. |

Avec des poids différents, la réduction à K ne vaut plus : chaque couverture singleton contribue selon son poids effectif. Les poids B/C/D et leurs réciproques ne doivent pas être remplacés par des fractions réelles idéales pour calculer des scores exacts.

Une extension suffisante est néanmoins démontrable : **au moins une position A de chacun des m lexèmes dans tout document complet** suffit à garantir un rang brut ≥ m, même si d’autres positions ont des poids inférieurs. En retirant ces contributions supplémentaires non négatives, il reste m additions exactes de 1 ; la monotonie de l’accumulation établit la borne. La formule R(K) n’est plus exacte dans ce domaine élargi, mais la dominance subsiste. Sans preuve de cet invariant, conserver le chemin général.

| Situation | Décision exacte |
|---|---|
| Domaine OR-A vérifié et au moins 50 complets | Top-50 de tous les complets, score et tri originaux ; pas de certificat numérique nécessaire. |
| Domaine vérifié mais moins de 50 complets | Ne pas retourner seulement ce sous-ensemble. Repli original, ou extension exacte décrite en section 6. |
| Positions absentes, poids inconnus, historique de construction non établi | Certificat général et repli, sous ses propres préconditions ; ne pas invoquer la dominance. |
| Phrase, préfixe, restriction de poids, négation, correspondance différente entre Q et les couvertures | La réduction OR-A ne s’applique pas. Certificat général ou preuve spécifique avant spécialisation. |
| Q impose déjà tous les lexèmes | C = D ; la restriction n’apporte aucune réduction, même si Q n’est pas OR pur. |
| Coefficients, normalisation, profondeur, types ou nombre maximal de termes modifiés | Refaire la preuve concernée ; aucune transposition implicite. |
| IDF négative/non finie, total nul/incohérent, score non fini | Ni cette preuve ni le certificat monotone P4 ne sont valides ; ne pas activer le raccourci et traiter l’invalidité selon le comportement H1. |

Une exclusion supplémentaire peut laisser subsister certaines bornes, mais ce rapport ne démontre pas la réduction du rang pour tous les arbres combinant OR et NOT. La garde doit porter sur le tsquery réel, pas sur une heuristique de son texte utilisateur.

## 6. Conséquences algorithmiques et comparaison avec P4

Soit D l’ensemble admissible original et C les documents de D couvrant tous les lexèmes. La preuve établit que chaque élément de C précède chaque élément de D\C. Elle ne dit pas que tous les éléments de C ont le même score.

| Propriété | Spécialisation par dominance | Certificat général P4 |
|---|---|---|
| Condition d’arrêt | Domaine prouvé et 50 résultats du vrai classement de C | 50 résultats de C et score du 50e strictement supérieur à la borne des incomplets |
| Rang natif | Conservé sur C | Conservé sur C |
| Score du 50e à comparer à une borne | Inutile dans le domaine prouvé | Nécessaire |
| Dépendance aux positions A | Invariant nécessaire, ou extension démontrée | Pas cette hypothèse ; bornes et IDF valides nécessaires |
| Cas où C a 50 documents mais où le certificat échoue | Impossible sous les préconditions et une borne P4 correctement construite | Possible hors du domaine de dominance |
| Gain principal | Éviter le classement des incomplets | Identique quand le certificat réussit |

La nouvelle preuve **ne prédit donc pas une accélération substantielle supplémentaire par rapport à un certificat P4 qui réussit déjà** : calculer au plus 32 bornes constantes coûte peu face aux scans. Elle apporte surtout une condition de succès structurelle, plus simple à raisonner et à tester. Un certificat conservé provisoirement comme contrôle croisé serait redondant mathématiquement, mais utile pour détecter une erreur de garde ou d’implémentation.

Dans une future exécution optimisée, le top-50 exact de C peut servir lui-même de contrôle de cardinalité : s’il retourne 50 lignes, C en contient au moins 50. **Aucun COUNT préalable n’est nécessaire en production.** Le COUNT n’est proposé ci-dessous que pour comprendre le potentiel de réduction.

Si le classement exhaustif de C retourne k < 50 lignes, une autre extension exacte devient possible dans le domaine prouvé : concaténer ces k lignes avec le top-(50−k) de D\C, chaque partie triée par le score H1 original et la collation C. La dominance justifie cette concaténation. Elle évite de renoter C mais ne garantit pas d’économiser le scan des incomplets. Un repli complet reste plus simple pour une première version. Ces étapes exigent un snapshot cohérent.

Il est incorrect de prendre 50 documents quelconques de C puis de les classer. La conjonction sert à réduire l’ensemble à classer, sans plafonnement arbitraire intermédiaire.

## 7. Autres pistes exactes, classées par intérêt

### 7.1 Supprimer les tests de couverture devenus constants dans C

Dans C, tous les CASE de présence valent vrai. Les composantes A* et b_m peuvent être évaluées une seule fois par requête, avec **le même arbre d’opérations et les mêmes valeurs liées**. Le rang demeure natif ; le score final demeure `RN64(RN64(A* + b_m) + RN64(c₂ × R))`.

Cette simplification évite les deux séries de tests `@@` de scoring pour les documents complets. Elle ne requiert ni changement des poids ni index supplémentaire. Son intérêt dépend du coût résiduel des couvertures et de |C|. Ne pas remplacer A*+b_m par la constante décimale 0,8 et ne pas réassocier les opérations. À tester **après** la restriction à C, séparément, avec parité binaire : sinon l’origine du gain serait moins lisible.

### 7.2 Compter les positions plutôt que construire des couvertures

La réduction R(K) pourrait permettre une fonction spécialisée qui consulte les listes de positions des seuls lexèmes recherchés. Elle éviterait une partie des allocations, tris et évaluations de couvertures de `ts_rank_cd`. Le coût de détoastage resterait à mesurer. Une expression SQL utilisant `unnest(tsvector)` peut au contraire allouer et parcourir davantage de données ; la preuve mathématique ne prouve aucun gain de cette implémentation.

La priorité reste inférieure à la restriction de candidats, qui conserve le code PostgreSQL existant. Une fonction native ou une représentation précomptée demanderait une étude et une validation propres, avec risques de déploiement ou de cohérence supplémentaires. Rien de tel n’est implémenté ou proposé à installer maintenant.

### 7.3 Ne pas confondre monotonie du rang et identité du classement

R(K) est croissant au sens large, **pas strictement croissant**. Un contrôle local des K de 1 à 8192 trouve la première collision adjacente à :

```text
K = 4140 et K = 4141
R(K) = 0,9997585415840149 dans les deux cas
```

Ces deux valeurs sont réalisables dans des documents complets dès m = 17, sous le plafond 256 positions par lexème. À couvertures identiques, les scores H1 sont égaux. `ORDER BY K DESC, document_id` changerait donc le départage si le document de K = 4140 possède l’identifiant prioritaire en collation C. Il faut préserver le score flottant final et son départage, même pour une future fonction de comptage exacte.

De même, la dominance des **complets** ne prouve pas un classement lexicographique de tous les documents par nombre de lexèmes couverts : les IDF des termes manquants peuvent différer fortement entre documents partiels.

## 8. Protocole minimal proposé — à autoriser séparément

### 8.1 Relevés légers et preuve d’applicabilité

Commencer par `democratie-02` uniquement. Réutiliser la capture exacte P1/P2/P3 des paramètres et du SQL, sans hydratation, modèle ou HNSW. Relever : requête normalisée, m, IDF et total, empreintes SQL/paramètres, identité et version du corpus, version PostgreSQL, paramètres effectifs JIT/work_mem/timeouts et filtres. Les valeurs privées restent dans les sorties privées.

Établir l’invariant des vecteurs à partir de la provenance de leur construction et de l’absence de chemins d’écriture divergents. **Un échantillon conforme ne prouve pas cet invariant pour tous les documents.** Si la provenance ne suffit pas, garder le certificat général tant qu’une vérification exhaustive autorisée, de préférence sur copie, n’a pas comblé ce manque.

Construire conceptuellement C en conservant le WHERE H1 complet et en ajoutant la conjonction des **mêmes lexèmes normalisés et échappés**. Une conjonction de présence ne remplace ni Q dans l’appel de rang ni les filtres originaux.

Avant toute mesure exécutante, comparer les `EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON)` des requêtes prévues : index, estimations, placements des expressions, agrégations et parallélisme. Ces plans sans ANALYZE restent eux aussi soumis à l’autorisation d’accès à Wallace.

### 8.2 Deux exécutions coûteuses pour une première réponse

| Exécution séparée | Résultat recherché | Limite d’interprétation |
|---|---|---|
| `SELECT count(*)` sur C, filtres et paramètres exacts | Cardinalité exacte et durée de sélection/agrégation observée côté client | Cette durée inclut COUNT et protocole client ; ce n’est pas un temps CPU pur du filtre. Son plan peut différer du classement. |
| `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT JSON)` du vrai top-50 de C | Coût de son véritable classement, lignes, loops, workers, buffers, tri et temps inclusifs | Garder l’expression H1 entière pour cette première mesure. EXPLAIN ne retourne pas les identifiants/scores sélectionnés. |

L’expression `count(*)` et le classement emploient le même ensemble C. La première exécution fournit la cardinalité réelle, que l’agrégat final d’un EXPLAIN ne donne pas directement comme résultat de COUNT. Si l’on veut aussi les temps et buffers du plan de sélection isolé, une **troisième exécution**, EXPLAIN ANALYZE du COUNT, sera nécessaire et annoncée comme telle. Ne pas la déclencher implicitement.

Les gains se jugent par |C|/|D|, le temps du vrai classement et le travail observé. Une forte diminution de candidats n’assure pas un gain proportionnel : parcours GIN, heap, TOAST et parallélisme peuvent changer. Les temps des nœuds sont inclusifs ; ne pas les additionner. Les hits/reads PostgreSQL ne mesurent pas directement les accès physiques au SSD.

Si |C| < 50, le consigner ; aucun repli coûteux ou autre requête n’est lancé automatiquement pendant le diagnostic. Le classement de C peut rester utile à mesurer, mais la condition de retour direct n’est pas remplie.

### 8.3 Validation d’exactitude et confirmation du gain

Avant adoption, exécuter séparément le SELECT original et celui restreint à C sur le **même snapshot**, sans hydratation. Comparer les identifiants dans l’ordre, les octets des scores float8 (par exemple via `float8send`) et le départage C. Une somme agrégée ou des décimales affichées ne suffisent pas. Conserver les résultats détaillés dans les fichiers privés et partager seulement le verdict de parité.

Inclure des cas synthétiques de positions communes/saturées, m = 1/2/5/32, termes répétés avant normalisation, IDF très déséquilibrées, collisions de rang, égalités à la frontière, moins de 50 complets, ainsi que les cas qui doivent refuser la spécialisation. Les contre-exemples sans positions et avec poids D doivent activer le chemin général. Vérifier ensuite RRF avec une liste vectorielle fixée, sans relancer d’encodeur.

Pour comparer les performances, effectuer ensuite des répétitions appariées original/restreint, en alternant l’ordre, à JIT et work_mem identiques et corpus stable. Ne pas comparer directement une nouvelle mesure chaude à un ancien temps froid P3. Les médianes, dispersions, statuts timeout, changements de plan et sélectivités doivent être rapportés ; les timeouts ne sont pas supprimés de l’analyse. Ni cette répétition ni `fiscalite-01` ne font partie d’un lancement automatique.

Protections à reprendre : rôle lecteur, transaction explicitement READ ONLY, rollback systématique, temps de connexion/verrouillage/requête et durée globale bornés, exécution séquentielle sans retry, sorties privées et bornées, synthèse expurgée. Pour les comparaisons nécessitant plusieurs SELECT, prévoir un snapshot commun, par exemple READ ONLY REPEATABLE READ, sans réglage permanent. Aucune expérimentation ni commande de campagne n’est exécutée par cet audit.

## 9. Vérifications réalisées et traces

Réalisé localement : lecture du moteur et des sources amont PostgreSQL, preuve par monotonie, calcul exact des 31 marges flottantes, recoupement des 31 conversions float32, recherche de collisions pour K ≤ 8192 et calcul des contre-exemples synthétiques. Aucun test de charge, aucun démarrage de PostgreSQL ou modèle ; aucune validation native sur le binaire de Wallace n’est revendiquée.

Empreintes SHA-256 des fichiers examinés :

```text
tsrank.c REL_17_11, source amont téléchargée pour lecture :
28d611144f2b8e81ca0f8e834f0cf48494f52d8b37f593743179cabc51573004

rag/src/cahier_rag/tuning/lexical.py :
d443c1f3b5ec1388d9ac0f56306086f029db9aee80804c82c239e288658b2d6b

rag/src/cahier_rag/search/preparation.py :
1c6cc9f096141ef19166b025870de2e1da04b2b4e466c86d32588aa3215ec55c
```

La priorité est désormais de vérifier l’applicabilité au corpus, puis la sélectivité de C. Si C est suffisamment petit, **restreindre les évaluations du rang natif à C** offre la première expérience la plus directe, avec une preuve de conservation du top-50. La simplification des couvertures constantes vient ensuite ; le remplacement natif du rang par un comptage reste une piste distincte et plus coûteuse à valider.
