Périmètre + maquettes hi‑fi mobile

DAL read‑only + mapping champs

Endpoints/fragments htmx (réponses → questions → thèmes)

Cache + rate‑limit + erreurs UX

SEO + accessibilité + analytics

Déploiement staging → prod

QA finale + go‑live

# Ingest

```
./gdn_ingest/target/release/gdn_ingest ingest   --db sqlite:///$PWD/gdn.db   --csv $PWD/data/la-fiscalite-et-les-depenses-publiques.csv   --mapping $PWD/ingest/mappings/fiscalite_depenses.yml   --batch fiscalite_depenses_$(date +%F)   --commit-every 20000   --log-every 2000   --defer-fts
[ingest] form id=3 name='Grand Débat - Fiscalité & dépenses publiques' version='v1
```


# Lancer l'app

`uvicorn app:app --reload --port 8000`