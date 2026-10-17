-- Audit agrégé local : aucun contenu citoyen brut renvoyé.
-- Les résultats peuvent être volumineux (histogrammes).
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='240s';
SET LOCAL lock_timeout='2s';
SET LOCAL work_mem='64MB';

-- schema
SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position;

-- constraints
SELECT conrelid::regclass::text AS table_name,conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2;

-- meta
SELECT now() AS snapshot,version(),current_database(),pg_database_size(current_database()) AS bytes, (SELECT version_num FROM alembic_version) AS migration;

-- forms
SELECT f.id,f.name,f.source,q.type,count(*) AS questions FROM forms f JOIN questions q ON q.form_id=f.id GROUP BY f.id,q.type ORDER BY f.id,q.type;

-- questions
SELECT q.id,q.form_id,q.question_code,q.type,q.position,q.prompt,st.answers_count FROM questions q LEFT JOIN question_stats st ON st.question_id=q.id ORDER BY q.form_id,q.position,q.id;

-- contributions
SELECT form_id,count(*) AS n,count(DISTINCT author_id) AS authors,count(*) FILTER(WHERE author_id IS NULL) AS no_author,min(submitted_at) AS first_date,max(submitted_at) AS last_date,count(*) FILTER(WHERE submitted_at IS NULL) AS no_date,count(*) FILTER(WHERE raw_json IS NOT NULL) AS raw,count(*) FILTER(WHERE title IS NULL OR btrim(title)='') AS no_title FROM contributions GROUP BY form_id ORDER BY form_id;

-- lengths
SELECT q.form_id,q.type,char_length(a.text) AS chars,count(*) AS n,sum(octet_length(a.text)) AS bytes FROM answers a JOIN questions q ON q.id=a.question_id GROUP BY q.form_id,q.type,char_length(a.text) ORDER BY 1,2,3;

-- per_question
SELECT a.question_id,count(*) AS n,sum(char_length(a.text)) AS chars,max(char_length(a.text)) AS max_chars,count(*) FILTER(WHERE a.text IS NULL OR btrim(a.text)='') AS empty,count(*) FILTER(WHERE char_length(a.text)<=20) AS le20,count(*) FILTER(WHERE char_length(a.text)>2000) AS gt2000,count(*) FILTER(WHERE char_length(a.text)>8000) AS gt8000 FROM answers a GROUP BY a.question_id;

-- choice_extra
SELECT q.form_id,q.type,count(*) AS n,count(*) FILTER(WHERE jsonb_array_length(coalesce(a.value_json::jsonb->'other_text','[]'::jsonb))>0) AS with_other,sum((SELECT coalesce(sum(char_length(v)),0) FROM jsonb_array_elements_text(coalesce(a.value_json::jsonb->'other_text','[]'::jsonb)) v)) AS other_chars,sum((SELECT count(*) FROM jsonb_array_elements_text(coalesce(a.value_json::jsonb->'other_text','[]'::jsonb)) v WHERE btrim(v)<>'')) AS other_items FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type IN ('single_choice','multi_choice') GROUP BY 1,2 ORDER BY 1,2;

-- titles
SELECT form_id,char_length(title) AS chars,count(*) AS n FROM contributions GROUP BY form_id,char_length(title) ORDER BY 1,2;

-- title_dup
SELECT form_id,count(*) AS distinct_titles,sum(n) AS occurrences,sum(n-1) AS excess,max(n) AS max_frequency,sum(n) FILTER(WHERE n>=10) AS in_groups_ge10 FROM (SELECT form_id,md5(title) AS fingerprint,count(*) AS n FROM contributions WHERE title IS NOT NULL AND btrim(title)<>'' GROUP BY form_id,md5(title)) t GROUP BY form_id ORDER BY form_id;

-- duplicates
SELECT form_id,type,count(*) AS distinct_fingerprints,sum(n) AS n,sum(n-1) AS excess,max(n) AS max_frequency,sum(n) FILTER(WHERE n>=10) AS in_groups_ge10,sum(n) FILTER(WHERE n>=100) AS in_groups_ge100 FROM (SELECT q.form_id,q.type,md5(a.text) AS fingerprint,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id GROUP BY q.form_id,q.type,md5(a.text)) d GROUP BY form_id,type ORDER BY 1,2;

-- dup_text_global
SELECT count(*) AS distinct_fingerprints,sum(n) AS n,sum(n-1) AS excess,max(n) AS max_frequency,sum(n) FILTER(WHERE n>1) AS in_duplicate_groups,sum(n) FILTER(WHERE n>=10) AS in_groups_ge10 FROM (SELECT md5(a.text) AS h,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text' GROUP BY md5(a.text)) d;

-- normalized_dup
SELECT count(*) AS distinct_fingerprints,sum(n) AS n,sum(n-1) AS excess,max(n) AS max_frequency,sum(n) FILTER(WHERE n>=10) AS in_groups_ge10 FROM (SELECT md5(lower(regexp_replace(btrim(a.text),'[[:space:]]+',' ','g'))) AS h,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text' GROUP BY 1) d;

-- parent_lengths
SELECT form_id,chars,n_answers,count(*) AS n FROM (SELECT q.form_id,a.contribution_id,sum(char_length(a.text)) AS chars,count(*) AS n_answers FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text' GROUP BY q.form_id,a.contribution_id) t GROUP BY form_id,chars,n_answers ORDER BY 1,2;

-- integrity
SELECT count(*) FILTER(WHERE q.form_id<>c.form_id) AS mismatched_forms,count(*) FILTER(WHERE a.position<>1) AS nonfirst_position FROM answers a JOIN questions q ON q.id=a.question_id JOIN contributions c ON c.id=a.contribution_id;

-- extensions
SELECT extname,extversion FROM pg_extension ORDER BY 1;

-- indexes
SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2;

-- triggers
SELECT event_object_table,trigger_name,action_statement FROM information_schema.triggers WHERE trigger_schema='public' ORDER BY 1,2;

-- other_lengths
SELECT q.form_id,q.type,char_length(v) AS chars,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id CROSS JOIN LATERAL jsonb_array_elements_text(coalesce(a.value_json::jsonb->'other_text','[]'::jsonb)) v WHERE q.type IN ('single_choice','multi_choice') AND btrim(v)<>'' GROUP BY 1,2,3 ORDER BY 1,2,3;

-- titles_flags
SELECT form_id,count(*) FILTER(WHERE lower(btrim(title)) IN ('sans titre','aucun','néant','neant','test','contribution','proposition','mes propositions')) AS generic,count(*) FILTER(WHERE btrim(title) ~ '^[[:digit:][:punct:][:space:]]+$') AS nonlexical FROM contributions GROUP BY form_id ORDER BY form_id;

-- author_flags
SELECT count(*) AS n,count(*) FILTER(WHERE zipcode IS NOT NULL AND btrim(zipcode)<>'') AS zipcode,count(*) FILTER(WHERE age_range IS NOT NULL AND btrim(age_range)<>'') AS age,count(*) FILTER(WHERE gender IS NOT NULL AND btrim(gender)<>'') AS gender,count(*) FILTER(WHERE name IS NOT NULL AND btrim(name)<>'') AS names FROM authors;

-- question_lengths
SELECT a.question_id,char_length(a.text) AS chars,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text' GROUP BY a.question_id,char_length(a.text) ORDER BY 1,2;

-- dup_question
SELECT question_id,count(*) AS distinct_fingerprints,sum(n) AS n,sum(n-1) AS excess,max(n) AS max_frequency,sum(n) FILTER(WHERE chars>=200 AND n>=2) AS repeated_long_occurrences,sum(n-1) FILTER(WHERE chars>=200 AND n>=2) AS repeated_long_excess FROM (SELECT a.question_id,md5(a.text) AS h,char_length(a.text) AS chars,count(*) AS n FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text' GROUP BY a.question_id,md5(a.text),char_length(a.text)) d GROUP BY question_id ORDER BY question_id;

-- title_only
SELECT c.form_id,count(*) AS n,count(*) FILTER(WHERE t.contribution_id IS NULL) AS no_free_text,count(*) FILTER(WHERE t.contribution_id IS NULL AND NOT EXISTS(SELECT 1 FROM answers a WHERE a.contribution_id=c.id)) AS no_answers FROM contributions c LEFT JOIN (SELECT DISTINCT a.contribution_id FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.type='text') t ON t.contribution_id=c.id GROUP BY c.form_id ORDER BY c.form_id;

ROLLBACK;
