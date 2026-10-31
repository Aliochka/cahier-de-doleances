# Travail courant et conservation

## Lire et vérifier

Lancer `python3 1789/review.py` depuis la racine. L’interface utilise le registre, le corpus initial et les journaux existants. Une validation humaine n’est jamais recréée à partir d’une annotation Codex ou d’une proposition OCR.

L’organisation reste : **notice documentaire → parent établi → article/section/passage → futur segment vectoriel**. La préparation de l’extraction globale n’autorise pas à traiter des notices d’annexe ou des parents incertains comme des cahiers complets.

## Emplacements de référence

| Usage | Emplacement unique |
|---|---|
| Transcriptions intégrales figées | `1789/sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602/` |
| Métadonnées Persée déjà collectées | `1789/sources/persee/` |
| Registre documentaire | `1789/data/registry/` |
| Parents et unités initiaux | `1789/data/article-corpus/` |
| Journaux Cahiers et Articles | `1789/data/private/document-review/` |
| Exports de vérification | `1789/data/review-exports/` |
| Propositions de segmentation distinctes | `1789/data/segmentation-proposals/` |
| Campagnes et méthodes de tirage | `1789/tools/document-review/campaigns/` |
| Résultats et conclusions des anciens audits | `1789/archives/` |

Les instantanés privés propres à un ancien audit restent dans son sous-dossier `.local/`, ignoré par Git. Ils sont des références d’expérience, pas le journal actif. Les décisions courantes ne doivent être écrites que dans les journaux actifs.

## Avant une extraction globale ultérieure

1. Sauvegarder les journaux et les sources nécessaires.
2. Figer une version du registre et des frontières retenues.
3. Préserver les unités humaines et leurs corrections comme contraintes explicites.
4. Produire une nouvelle version de corpus sous `1789/data/corpus/<version>/` ; conserver la correspondance avec les identifiants antérieurs.
5. Évaluer anomalies, couverture et articles non signalés selon le protocole du bilan humain.
6. Distinguer les articles historiques, passages techniques et segments vectoriels ; conserver les statuts et l’accès au parent.

Aucune de ces opérations d’extraction ou d’indexation n’est effectuée par le déplacement de dossiers.

## Sauvegardes et Git

Les journaux contiennent des décisions personnelles et un historique non remplaçable par réextraction. Sauvegarder **au minimum `1789/data/private/`** dans un emplacement privé. Pour une restauration complète du travail, conserver aussi les sources et données locales exclues de Git ainsi que les instantanés d’audit nécessaires. Aucune sauvegarde externe n’a été créée par cette réorganisation.

Ne pas utiliser `git add -f` sur les sources ou journaux. Les petites métadonnées et métriques qui étaient versionnées restent autorisées explicitement ; les corpus complets, les tableaux numériques et les décisions nominatives restent locaux.

Les modèles BGE-M3 et Qwen sont des ressources partagées sous `rag/`. Les commandes historiques qui les utilisent peuvent nécessiter leur environnement d’origine ; la réorganisation ne les télécharge ni ne lance d’inférence.
