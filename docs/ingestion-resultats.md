# Import complet du Grand Débat National

Vérifié le 2026-10-10T10:20:41.992729+00:00.

Les sept exports JSON officiels ont été comparés aux CSV : mêmes identifiants, même ordre et même nombre de contributions. Les différences de cellules CSV sont comptées ci-dessous ; les valeurs JSON originales sont conservées.

| Formulaire | Contributions | Questions | Réponses | Liens vers les choix | Questions multiples | Différences CSV/JSON |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Grand Débat - Organisation de l'État & services publics | 111953 | 33 | 1418756 | 565836 | 0 | 55 |
| Grand Débat - Démocratie & citoyenneté | 116549 | 37 | 2768451 | 636050 | 0 | 65 |
| Grand Débat - Fiscalité & dépenses publiques | 186711 | 8 | 1101582 | 189150 | 1 | 81 |
| Grand Débat - Transition écologique | 153809 | 16 | 1857421 | 802260 | 1 | 46 |
| Grand Débat - Organisation de l'État & services publics (questions rapides) | 333793 | 12 | 3907624 | 4407167 | 3 | 0 |
| Grand Débat - Démocratie & citoyenneté (questions rapides) | 335157 | 7 | 2304821 | 2561430 | 1 | 0 |
| Grand Débat - Transition écologique (questions rapides) | 351313 | 7 | 2434095 | 2519985 | 1 | 0 |

Taille PostgreSQL au contrôle : **14 GB**.

Caractères nuls remplacés dans le texte affiché/indexé : **4**. Les originaux restent dans `contributions.raw_json` et les fichiers téléchargés.

Contrôles validés : empreintes des sources, import terminé pour les sept fichiers, couverture exacte des questions, une réponse par contribution/question (position 1 et contrainte unique), liens vers les options sans perte ni doublon, catalogues limités aux labels officiels, compteurs par question et compteur global cohérents.

## Provenance

- [organisation_etat_services](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-233406/organisation-de-letat-et-des-services-publics-1-.json) — ressource `7164c640-0a24-479c-a2cc-4aaad72d4b53` — SHA-256 `306ec8805a1c1f162b36d538b456ffefc9a4347973b1c1eeb40ae1f7f7da1687`.
- [democratie_citoyennete](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-225028/democratie-et-citoyennete.json.zip) — ressource `2e6a15ba-98e1-4dca-a406-47d64d64809e` — SHA-256 `35600356703615423e2cf514e97b5ddd048596203c5d6e035eacbe21b05aaedc`.
- [fiscalite_depenses](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-214232/la-fiscalite-et-les-depenses-publiques.json) — ressource `f5b05574-a70c-45c5-92a8-d3d85a899f2f` — SHA-256 `9b62a77feeac824184a80be5bde491d95d6da1510e30a1cabb093e0898cd68f2`.
- [transition_ecologique](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-181926/la-transition-ecologique.json) — ressource `cfe1c622-88db-483b-a36b-9423504a7020` — SHA-256 `c4dc46ef349ab69df617af882491d246a7b468fe7d10c51ee1e38c96e066ca4a`.
- [questions_rapides_organisation](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-234421/questionnaire-organisation-de-letat-et-des-services-publics.json) — ressource `16c0eccb-b8e7-4be4-a720-742aac8dabbf` — SHA-256 `ff0f1cd134b6bc95357ff5961d134f14b71805183b0fbd10588dac2bf39630ef`.
- [questions_rapides_democratie](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-225219/questionnaire-democratie-et-citoyennete.json) — ressource `02a8e332-cfe1-4bd9-b8f7-1e60d16d9de0` — SHA-256 `015f3e64d5a1f5d1ae6c9c345fbaaca8f95bd8c632b74cbbeb7abc0e7e25df80`.
- [questions_rapides_transition](https://static.data.gouv.fr/resources/donnees-ouvertes-du-grand-debat-national/20200611-215010/questionnaire-la-transition-ecologique.json) — ressource `096e133e-e727-49be-a3a2-bc9e9322f8ce` — SHA-256 `268a9336195f942c9b1cf132a0052ef3fad0b78819c6a0e94a8cde743cd6f5d2`.
