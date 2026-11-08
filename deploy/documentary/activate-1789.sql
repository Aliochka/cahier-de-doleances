-- PREPARED ONLY. Separate, future human publication approval is MANDATORY.
-- psql variables required: authorize_publication, approval_id, approval_sha256, decided_by, approved_at.
-- The file identified by approval_sha256 must be retained with the deployment.
-- No historical text, passage, vector, lexical statistic or GDN object is modified.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='15s';
DO $$
BEGIN
  IF current_database()<>'cahier_search'
     OR (SELECT oid FROM pg_database WHERE datname=current_database())<>634726
     OR (SELECT system_identifier::text FROM pg_control_system())<>'7695026423032606758'
     OR current_user<>'cahier'
     OR (SELECT version_num FROM public.rag_alembic_version) IS DISTINCT FROM 'rag_0007' THEN
    RAISE EXCEPTION 'Physical production destination, role or revision mismatch';
  END IF;
END $$;
SET LOCAL ROLE cahier_documentary_owner;
SELECT set_config('cahier.approval.id', :'approval_id', true),
       set_config('cahier.approval.authorized', :'authorize_publication', true),
       set_config('cahier.approval.sha256', :'approval_sha256', true),
       set_config('cahier.approval.by', :'decided_by', true),
       set_config('cahier.approval.at', :'approved_at', true);
SELECT pg_advisory_xact_lock(1789,1);
DO $$
DECLARE r documentary.release%ROWTYPE;
BEGIN
  IF current_setting('cahier.approval.authorized')<>'true'
     OR current_setting('cahier.approval.id') !~ '^[a-zA-Z0-9][a-zA-Z0-9._-]{7,79}$'
     OR current_setting('cahier.approval.sha256') !~ '^[0-9a-f]{64}$'
     OR current_setting('cahier.approval.sha256')=repeat('0',64)
     OR length(trim(current_setting('cahier.approval.by')))<3
     OR current_setting('cahier.approval.at')::timestamptz>now() THEN
    RAISE EXCEPTION 'Explicit publication approval identity, fingerprint and author required';
  END IF;
  SELECT * INTO STRICT r FROM documentary.release
    WHERE corpus_id='cahiers-1789-ap-stanford'
      AND release_id='reference-documents-2-7cbcaea79991' FOR UPDATE;
  IF r.source_manifest_hash<>'eb9f4533e95df62a8964fbd6a71d56c0446b7769f6fa9d80fcdd8c0111e08ff2'
     OR r.editorial_hash<>'2b2b4c14e33ed5b7908a7e0304a980143c803c088af5dd8234690a81a8314cba'
     OR r.state<>'verified' OR r.publication_authorized
     OR NOT r.representations_ready OR NOT r.statistics_ready
     OR (r.lexical_statistics->>'units')::int IS DISTINCT FROM 10748
     OR r.lexical_statistics->>'editorial_hash' IS DISTINCT FROM r.editorial_hash
     OR r.embedding_recipe#>>'{model,revision}' IS DISTINCT FROM '5617a9f61b028005a4858fdac845db406aefb181'
     OR (SELECT active_release_id FROM documentary.corpus WHERE corpus_id=r.corpus_id) IS NOT NULL THEN
    RAISE EXCEPTION 'Only the verified, unpublished, compatible 1789 release can be promoted';
  END IF;
  IF (SELECT count(*) FROM documentary.document WHERE corpus_id=r.corpus_id AND release_id=r.release_id)<>1267
     OR (SELECT count(*) FROM documentary.document WHERE corpus_id=r.corpus_id AND release_id=r.release_id AND candidate)<>1224
     OR (SELECT count(*) FROM documentary.search_unit WHERE corpus_id=r.corpus_id AND release_id=r.release_id)<>11391
     OR (SELECT count(*) FROM documentary.search_unit u JOIN documentary.document d USING(corpus_id,release_id,document_id)
         WHERE u.corpus_id=r.corpus_id AND u.release_id=r.release_id AND d.candidate AND u.searchable
           AND u.embedding IS NOT NULL AND u.search_vector IS NOT NULL)<>10748
     OR (SELECT count(*) FROM documentary.search_unit WHERE corpus_id=r.corpus_id AND release_id=r.release_id AND NOT searchable)<>2
     OR (SELECT count(*) FROM documentary.search_unit WHERE corpus_id=r.corpus_id AND release_id=r.release_id AND NOT searchable
         AND unit_id IN ('ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c','ap1789-technical-passage-1:32ae8c839247d77b503fba421372'))<>2
     OR EXISTS(SELECT FROM documentary.document WHERE corpus_id=r.corpus_id AND release_id=r.release_id AND (readable OR searchable OR catalogue_visible))
     OR EXISTS(SELECT FROM documentary.editorial_decision WHERE corpus_id=r.corpus_id AND property='publication') THEN
    RAISE EXCEPTION 'Publication perimeter, Artois exclusions or prior publication state differs';
  END IF;
END $$;
INSERT INTO documentary.editorial_decision
 (decision_id,revision_id,sequence,corpus_id,source_generation,document_id,unit_id,
  expected_document_hash,expected_extent_id,expected_unit_hash,property,value,
  reason_code,justification,evidence,decided_by,decided_at,supersedes_id)
SELECT current_setting('cahier.approval.id')||':'||document_id,
       current_setting('cahier.approval.id'),row_number() OVER(ORDER BY edition_order)::int,
       corpus_id,release_id,document_id,NULL,text_sha256,extent_id,NULL,'publication',
       '{"catalogue":true,"read":true,"search":true}'::jsonb,
       'explicit_initial_publication_authorization',
       'Autorisation publique du périmètre candidat ; ne constitue pas une certification historique.',
       jsonb_build_object('approval_id',current_setting('cahier.approval.id'),
                          'approval_sha256',current_setting('cahier.approval.sha256'),
                          'scope','1224 candidate cahiers; 43 other documents remain unpublished'),
       current_setting('cahier.approval.by'),current_setting('cahier.approval.at')::timestamptz,NULL
FROM documentary.document
WHERE corpus_id='cahiers-1789-ap-stanford' AND release_id='reference-documents-2-7cbcaea79991' AND candidate;
UPDATE documentary.document SET readable=true,searchable=true,catalogue_visible=true
WHERE corpus_id='cahiers-1789-ap-stanford' AND release_id='reference-documents-2-7cbcaea79991' AND candidate;
UPDATE documentary.release SET state='ready',publication_authorized=true
WHERE corpus_id='cahiers-1789-ap-stanford' AND release_id='reference-documents-2-7cbcaea79991';
UPDATE documentary.corpus SET active_release_id='reference-documents-2-7cbcaea79991'
WHERE corpus_id='cahiers-1789-ap-stanford';
COMMIT;
