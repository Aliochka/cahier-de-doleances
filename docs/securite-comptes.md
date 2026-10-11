# Écritures et réponses privées

Les écritures `/auth/send-link`, `/auth/logout`, `/auth/complete-profile` et
`/bookmarks/*` exigent une origine exacte autorisée, même sans session. `BASE_URL`
est autorisée automatiquement. `CSRF_TRUSTED_ORIGINS` permet de déclarer des
origines supplémentaires séparées par des virgules (schéma, hôte et port).

Pour un accès LAN, utiliser son `BASE_URL` ou ajouter explicitement son origine.
Même règle pour un autre port de développement et les prévisualisations Netlify :
déclarer chaque URL de prévisualisation contrôlée, jamais `*.netlify.app` ni un
suffixe de domaine. Ne pas autoriser des prévisualisations de code non fiable à
utiliser les sessions de production. Aucun changement de configuration de
production n'est effectué par cette tâche.

Sans `Origin`, seul un `Referer` de la même liste est accepté. Une origine absente,
opaque (`null`), malformée, multiple ou refusée renvoie 403. Un `Origin` refusé ne
peut pas être remplacé par un `Referer` autorisé. Les clients non navigateurs et
les futurs appels SSR doivent transmettre l'origine autorisée ; le proxy doit
préserver l'origine du navigateur, jamais la réécrire pour contourner le contrôle.
Les liens magiques restent des liens GET utilisables depuis les courriels.

Les routes comptes et marque-pages, les requêtes contenant un cookie de session
(même expiré) et les réponses définissant des cookies renvoient
`Cache-Control: private, no-store`, erreurs comprises. Le proxy Netlify devra
préserver cet en-tête et les `Set-Cookie`, sans règle de cache forcée sur ces
réponses. Les ressources publiques sans cookie conservent leur politique actuelle.
