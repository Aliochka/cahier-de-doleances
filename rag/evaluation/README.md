# Requêtes et annotations

`queries.json` contient 40 requêtes françaises rédigées manuellement, sans texte
extrait du corpus : dix par domaine, vingt pour le développement et vingt pour
l’évaluation finale. Six catégories sont présentes dans les deux partitions.
La famille regroupe les formulations apparentées ; elle ne traverse pas les
partitions. Cette liste initiale est une proposition de protocole, pas une
mesure de fréquence réelle des usages. Elle doit être revue humainement avant
le gel de la version finale et avant tout réglage de moteur.

Seul ce jeu de requêtes est explicitement autorisé par `.gitignore`.
Les manifestes locaux, candidats et annotations doivent rester dans `local/`,
ignoré par Git. Les JSONL du sous-projet sont ignorés également. Aucune
annotation humaine réelle n’est fournie et aucune note n’a été inventée.

Voir [le protocole complet](../evaluation.md).
