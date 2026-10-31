# Évaluation indépendante du tri — protocole proposé

Ce protocole est **préparé, non exécuté**. Aucun nouveau lot n’est tiré et aucun résultat de précision/rappel indépendant n’est annoncé.

## Question prioritaire

Combien d’erreurs graves subsistent dans les articles considérés comme peu risqués, et combien d’articles manquent entièrement dans les plages non segmentées ? Vérifier seulement les alertes ne permet pas d’y répondre.

## Gel et référence

Avant annotation : figer sources, parents, unités initiales, règles d’alerte, catégories, files de voisinage, identifiants, algorithme de tirage et graines. **Exclure les dix cahiers examinés de la nouvelle évaluation**. Ne pas retoucher les règles sur les erreurs du lot de validation ; ouvrir une nouvelle itération et un autre lot si nécessaire.

La référence doit être établie par un lecteur humain dans le texte parent, avec accès à la numérisation en cas d’ambiguïté. Le lecteur établit d’abord les unités attendues sans voir les étiquettes de risque lorsque c’est praticable, puis les compare aux propositions. Prévoir une seconde lecture d’une partie des cas et de tous les désaccords graves. Une annotation Codex seule ne constituerait pas cette validation indépendante.

## Calibrage limité sur les ressources actuelles

| Ensemble | Plan proposé | Ce qu’il mesure |
|---|---|---|
| Non-alertés hors de la file de contexte | Tirage uniforme sans remise de **100 parmi les 328** ; graine `1789333`, identifiants triés avant `random.Random(seed).sample` | Erreurs graves ou mineures non signalées, sur ce cadre local uniquement |
| Alertés | Examiner les **40** unités signalées des 19 cahiers et leurs voisins (69 unités distinctes) | Alertes pertinentes, avertissements légitimes mais non correctifs, fausses alertes et coût du contexte |
| Texte parent / C | **20 fenêtres continues** choisies indépendamment des débuts d’articles, dans les 19 parents ; graine `1789334` | Articles totalement manqués, prose, notes et complétude. Définir les fenêtres sur les blocs source, pas seulement sur les candidats |
| Bloqués | Aucun article bloqué dans les 29 parents initiaux ; sélectionner ultérieurement **10 dossiers parentaux bloqués/incertains** du registre, graine `1789335` | Justesse du blocage et problème de périmètre, séparément de la segmentation d’article |

Les cadres exacts seront gelés au lancement ; si des validations nouvelles ont eu lieu, utiliser un état versionné explicite et ne pas remplacer silencieusement des dossiers. Enregistrer les probabilités de sélection et la concentration par cahier. Les résultats de la strate bloquée ne sont pas mélangés aux taux d’erreur sur les articles. La file de contexte n’a pas à recevoir 69 validations automatiques : seule la lecture effectivement réalisée est enregistrée.

Ces 19 cahiers sont extérieurs aux dix revus par l’utilisateur, mais appartiennent encore au corpus pilote déjà étudié. Ils ne suffisent pas pour démontrer une généralisation à des milliers de cahiers.

## Mesures à publier

- Erreurs graves : fusion/omission d’une unité historique étayée, fausse séparation d’une unité, texte d’un autre parent. Les différences de ponctuation, blancs, numéro seul et qualification interprétative sont comptées séparément.
- Dans chaque strate : unités effectivement lues, nombre d’erreurs, décisions incertaines et temps humain déclaré/mesuré selon sa provenance.
- Proportion de cas signalés nécessitant réellement une correction de segmentation ; séparer une alerte de numéro historique légitime d’un faux découpage.
- Part des erreurs graves avec signal direct, signal voisin, signal uniquement manuel et sans signal.
- Erreurs manquées dans les fenêtres parentales, avec un dénominateur de texte examiné ; ne pas inventer un rappel exhaustif à partir de la seule liste des articles trouvés.
- Charge ciblée, charge d’échantillonnage, travail sur les parents. Ne pas mélanger les échantillons stratifiés en un taux global sans les pondérations de tirage adaptées.

## Critères préalables de décision

Pour un **premier index expérimental local**, seuils proposés à ratifier avant le test :

1. Aucun dépassement de parent, chevauchement incompatible, texte altéré ou référence cassée ; toutes les décisions humaines réappliquées correctement.
2. Aucun cas grave non résolu dans le lot exporté ; toutes les anomalies ciblées traitées ou exclues.
3. **Zéro erreur grave observée dans les 100 non-alertés** et aucune omission grave trouvée dans les 20 fenêtres parentales. Une seule erreur grave suffit à suspendre l’exemption de relecture pour la famille concernée et ouvrir une itération distincte.
4. Incertitudes, exclusions, faux positifs et coûts documentés, même si les seuils précédents sont satisfaits.
5. Premier lot limité à **2 000 unités maximum**, surveillé et reproductible, sans publication automatique.

Ces seuils sont une **politique d’essai conservatrice**, pas la preuve d’un taux d’erreur nul ou inférieur à un seuil statistique. L’échantillon est petit, les textes sont groupés par cahier, et certaines erreurs sont rares ou structurelles.

Avant publication élargie : prévoir une nouvelle campagne sur **au moins 30 nouveaux parents**, avec une cible de 300 articles non-alertés, des cas signalés et des fenêtres parentales. Vérifier la couverture des familles documentaires et la stabilité entre lots. Choisir alors explicitement le risque résiduel acceptable ; ne pas déduire une garantie sur les 1 305 notices d’une absence d’erreur sur quelques documents.

## Suivi permanent envisagé

Après calibration satisfaisante : vérifier les unités signalées et leur contexte ; tirer régulièrement **10 % des autres unités**, sans minimum dérisoire par lot, en renouvelant les parents et volumes. C’est un point de départ à ajuster selon le coût et les erreurs effectivement observées, pas une fréquence optimisée par cette mission. Une nouvelle famille d’OCR, un changement d’extracteur ou une correction parentale impose un contrôle renforcé.
