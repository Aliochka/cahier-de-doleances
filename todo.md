# ✅ SEO – Roadmap

## 🎯 v0+ (socle technique propre)
Objectif : que le site soit indexable et lisible par Google.  

- [x] **Balises `<title>` dynamiques**
  - Accueil, question, réponse, auteur  
  - Toujours unique, suffixé par “Cahier de doléances”  

- [x] **Balises `<meta description>` dynamiques**
  - Exemple : `"Découvrez les contributions citoyennes à la question {titre}."`  

- [x] **Balise `<h1>` unique par page**  
  - Titre de la question ou de la réponse  

- [x] **Sitemap XML** (`/sitemap.xml`)  
  - Liste : accueil, questions, réponses, auteurs  

- [x] **robots.txt** (`/robots.txt`)  
  - Avec lien vers sitemap  

- [x] **Canonical URL** sur chaque page  
  - Évite duplicate content  

- [ ] **Open Graph / Twitter Cards (version minimale)**  
  - `og:title`, `og:description`, `og:url`, `og:image`  

---

## 🚀 v1 (SEO + contenu + performance)  
Objectif : mieux se positionner sur des requêtes et améliorer l’expérience de recherche.  

- [ ] **URLs propres avec slug**  
  - `/questions/42-education-culture`  
  - `/auteurs/dupont-jean`  

- [ ] **Page d’accueil enrichie**  
  - Texte explicatif sur le projet, ses objectifs, et comment participer  
  - Liens internes vers les questions principales  

- [ ] **Améliorer l’UX de lecture**  
  - Meilleure typographie (espacement, lisibilité mobile)  
  - Mise en avant des contributions longues  

- [ ] **Balises sémantiques**  
  - `<article>`, `<section>`, `<header>`, `<footer>` autour des contenus  

- [ ] **Données structurées (schema.org)**  
  - Type `"Question"` pour les questions  
  - Type `"Answer"` pour les réponses  
  - Permet rich snippets dans Google  

- [ ] **Texte alternatif (alt) sur images** (si tu en ajoutes plus tard)  

- [ ] **Vitesse**
  - Vérifier via PageSpeed Insights  
  - Optimiser si besoin (lazyload, cache headers, compression)  

- [ ] **Suivi**
  - Google Search Console : soumettre sitemap, suivre indexation  
  - Analytics / Matomo : suivre trafic et requêtes  

# ✅ Checklist d’implémentation — Recherche & Page Formulaire

> Copie-colle tel quel. Aucune section n’impose du code ici.

## 0) Préparation
- [x] Sauvegarder la version actuelle.
- [x] Créer une branche `feat/search-forms-questions`.

---

## 1) Données & Index
- [x] Vérifier le modèle (Forms/Questions/Answers/Contributions) conforme à celui fourni.
- [x] Index DB :
  - [x] `questions(form_id, position)`
  - [x] `answers(question_id)`
  - [x] `answers(contribution_id, question_id)`
  - [x] `contributions(form_id, submitted_at, id)`
- [x] FTS :
  - [x] `question_fts(prompt)` (FR, unaccent)
  - [x] `form_fts(name)` (FR, unaccent)
- [x] Compteur rapide :
  - [x] Source pour **nb de réponses par question** (vue matérialisée ou table compteur + triggers).
- [ ] Synonymes FR (liste courte, extensible) :
  - [ ] Initialiser un petit lexique (éducation↔école, impôt↔fiscalité, climat↔environnement, etc.).
- [ ] Fallback tolérance fautes :
  - [ ] Dispositif **trigram** (table auxiliaire légère) sur `forms.name` et `questions.prompt`.

---

## 2) Route & Contrat de la page de recherche
- [ ] Conserver la route **`/search/questions`** (GET).
- [ ] Paramètres :
  - [ ] `q` (string) — conservé dans l’URL pour partage/SEO.
  - [ ] Pagination indépendante **par section** (ex. `page_forms`, `page_questions`).
- [ ] Réponse (côté serveur) — 2 collections :
  - [ ] **Formulaires** : `id`, `name`, `questions_count`.
  - [ ] **Questions** : `id`, `prompt_highlighted`, `answers_count`.
- [ ] Tri : **strictement BM25** pour chaque section.

---

## 3) Mécanique de recherche “généreuse”
- [ ] Normaliser les requêtes : lowercase + unaccent.
- [ ] Expansion :
  - [ ] Préfixes (ex. `écolo*`).
  - [ ] Synonymes (ajout de tokens équivalents).
- [ ] FTS5 :
  - [ ] Interroger `form_fts(name)` et `question_fts(prompt)`.
  - [ ] Récupérer score BM25 + `highlight()` pour Questions (titre uniquement).
- [ ] Fallback fautes :
  - [ ] Si trop peu de matches FTS : candidates via **trigram** → re-score via FTS (BM25) → limiter au top N.
- [ ] Performance :
  - [ ] Limites par lot (20/section).
  - [ ] Debounce côté client (200–300 ms).
  - [ ] Cache LRU 5–10 s (clé = requête normalisée).

---

## 4) UI/UX — Page Recherche
- [ ] Barre de recherche :
  - [ ] Saisie + debounce (200–300 ms).
  - [ ] Affichage de la requête et suppression rapide (X).
- [ ] **Section “Formulaires”** :
  - [ ] Carte : icône formulaire (stack/list), **Titre**, sous-ligne “Contient N questions”.
  - [ ] Action par item : **“Voir le formulaire”** → `/forms/{form_id}`.
  - [ ] **Scroll infini** par section (lot 20).
- [ ] **Section “Questions”** :
  - [ ] Ligne/carte : **Titre** avec surlignage (pas d’extrait).
  - [ ] **Badge “0 réponse”** si `answers_count = 0`.
  - [ ] Lien toujours actif vers la **page détail question**.
  - [ ] **Scroll infini** par section (lot 20).
- [ ] Empty state :
  - [ ] Message simple si 0 résultat dans les deux sections.
- [ ] Accessibilité :
  - [ ] Roles/aria, focus visible, contraste badges.
- [ ] Langue :
  - [ ] FR uniquement.

---

## 5) Nouvelle page — **Formulaire** `/forms/{form_id}`
- [ ] Header :
  - [ ] **Titre** du formulaire (name).
  - [ ] **Compteur** : “N questions”.
- [ ] Liste ordonnée des questions (Q1 → Qn) :
  - [ ] Afficher `position` + `prompt`.
  - [ ] Chaque item **lien** vers page **détail question**.
- [ ] Bloc **Contributions** :
  - [ ] Afficher **toutes les réponses** d’une **contribution** (ordre des questions).
  - [ ] Navigation :
    - [ ] Flèche **précédent** / **suivant** entre contributions du **même formulaire**.
    - [ ] Bornes claires (1..M).
  - [ ] Lien partageable :
    - [ ] Paramètre d’URL **`?contrib={index}`** (index lisible dans l’ordre `submitted_at ASC, id ASC`).
- [ ] Pas de stats détaillées par question (pour l’instant).

---

## 6) États/Erreurs/Chargement
- [ ] Indicateur de chargement discret par section.
- [ ] Gestion des erreurs réseau (toast bref).
- [ ] Pas de blocage inter-section (chargements indépendants).

---

## 7) Télémétrie minimale (pour itérations)
- [ ] Latence médiane / P95 de `/search/questions` par section.
- [ ] % requêtes utilisant le fallback **trigram**.
- [ ] CTR par type (Formulaire vs Question).
- [ ] Navigation contributions : usage des flèches, profondeur moyenne parcourue.

---

## 8) Tests d’acceptation
- [ ] “écolo” → trouve “écologie” (préfixe) dans **les deux sections**.
- [ ] “ecole” → trouve “école/éducation” (unaccent + synonymes).
- [ ] faute simple “educaiton” → résultats pertinents (fallback trigram → re-score BM25).
- [ ] Une **Question** avec 0 réponse :
  - [ ] Affiche le **badge “0 réponse”**.
  - [ ] Lien **actif** vers la question.
- [ ] Page Formulaire :
  - [ ] Affiche **N questions**, ordre Q1→Qn correct.
  - [ ] Affiche toutes les réponses de la contribution courante.
  - [ ] Flèches précédent/suivant fonctionnent et respectent les bornes.
  - [ ] URL `?contrib=7` ouvre la **7ᵉ contribution** de ce formulaire.
- [ ] Accessibilité :
  - [ ] Focus visible sur éléments interactifs.
  - [ ] Contraste badge/lien suffisant.

---

## 9) Livraison
- [ ] QA rapide (env de test).
- [ ] Merge → déploiement.
- [ ] Monitoring post-déploiement (latence, erreurs, CTR).

---

## 10) Suivi (prochaines itérations — optionnel)
- [ ] Page “Overview” formulaire (stats).
- [ ] Amélioration liste synonymes FR.
- [ ] Ajout paramètre stable `?contrib_id=` (sans casser `?contrib=`).
- [ ] Badges “1 réponse / N réponses” (si souhaité plus tard).
