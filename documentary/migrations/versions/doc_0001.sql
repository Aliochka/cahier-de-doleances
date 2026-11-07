-- Only on an explicitly identified, isolated local maintenance connection.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE documentary.corpus (
    corpus_id text PRIMARY KEY,
    slug text NOT NULL UNIQUE CHECK (length(slug)>0),
    label text NOT NULL,
    description text NOT NULL DEFAULT '',
    metadata jsonb NOT NULL DEFAULT '{}',
    active_release_id text
);
CREATE TABLE documentary.release (
    corpus_id text NOT NULL REFERENCES documentary.corpus,
    release_id text NOT NULL,
    source_generation text NOT NULL,
    source_manifest jsonb NOT NULL,
    source_manifest_hash text NOT NULL CHECK (source_manifest_hash ~ '^[0-9a-f]{64}$'),
    source_inventory jsonb NOT NULL,
    editorial_revision text NOT NULL,
    editorial_hash text NOT NULL CHECK (editorial_hash ~ '^[0-9a-f]{64}$'),
    lexical_recipe jsonb NOT NULL DEFAULT '{}',
    embedding_recipe jsonb NOT NULL DEFAULT '{}',
    lexical_statistics jsonb NOT NULL DEFAULT '{}',
    counts jsonb NOT NULL,
    state text NOT NULL DEFAULT 'loading' CHECK (state IN ('loading','verified','ready')),
    representations_ready boolean NOT NULL DEFAULT false,
    statistics_ready boolean NOT NULL DEFAULT false,
    publication_authorized boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    validated_at timestamptz,
    PRIMARY KEY (corpus_id,release_id),
    CHECK (state <> 'ready' OR (representations_ready AND statistics_ready)),
    CHECK (state = 'loading' OR validated_at IS NOT NULL)
);
ALTER TABLE documentary.corpus ADD CONSTRAINT corpus_active_release_fk
    FOREIGN KEY (corpus_id,active_release_id)
    REFERENCES documentary.release(corpus_id,release_id);

CREATE TABLE documentary.document (
    corpus_id text NOT NULL,
    release_id text NOT NULL,
    document_id text NOT NULL,
    extent_id text NOT NULL,
    source_title text NOT NULL CHECK (length(source_title)>0),
    full_text text NOT NULL,
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    source_metadata jsonb NOT NULL,
    provenance jsonb NOT NULL,
    edition_order bigint NOT NULL CHECK (edition_order>0),
    order_locator jsonb NOT NULL,
    document_kind text NOT NULL,
    boundary_status jsonb NOT NULL,
    display_title text NOT NULL CHECK (length(display_title)>0),
    warnings jsonb NOT NULL DEFAULT '{}',
    candidate boolean NOT NULL DEFAULT false,
    catalogue_visible boolean NOT NULL DEFAULT false,
    readable boolean NOT NULL DEFAULT false,
    searchable boolean NOT NULL DEFAULT false,
    metadata_vector tsvector,
    filter_metadata jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (corpus_id,release_id,document_id),
    UNIQUE (corpus_id,release_id,edition_order),
    FOREIGN KEY (corpus_id,release_id) REFERENCES documentary.release,
    CHECK (NOT searchable OR readable),
    CHECK (NOT catalogue_visible OR readable)
);
CREATE TABLE documentary.search_unit (
    corpus_id text NOT NULL,
    release_id text NOT NULL,
    unit_id text NOT NULL,
    document_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>0),
    unit_type text NOT NULL,
    start_offset integer NOT NULL CHECK (start_offset>=0),
    end_offset integer NOT NULL CHECK (end_offset>start_offset),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    source_metadata jsonb NOT NULL,
    searchable boolean NOT NULL DEFAULT true,
    search_vector tsvector,
    embedding public.vector(1024),
    embedding_hash text CHECK (embedding_hash ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (corpus_id,release_id,unit_id),
    UNIQUE (corpus_id,release_id,document_id,ordinal),
    FOREIGN KEY (corpus_id,release_id,document_id) REFERENCES documentary.document,
    CHECK ((embedding IS NULL) = (embedding_hash IS NULL))
);
CREATE TABLE documentary.editorial_decision (
    decision_id text PRIMARY KEY,
    revision_id text NOT NULL,
    sequence integer NOT NULL CHECK (sequence>0),
    corpus_id text NOT NULL REFERENCES documentary.corpus,
    source_generation text NOT NULL,
    document_id text NOT NULL,
    unit_id text,
    expected_document_hash text NOT NULL CHECK (expected_document_hash ~ '^[0-9a-f]{64}$'),
    expected_extent_id text NOT NULL,
    expected_unit_hash text CHECK (expected_unit_hash ~ '^[0-9a-f]{64}$'),
    property text NOT NULL CHECK (property IN ('search_enabled','display_title','warning','publication')),
    value jsonb NOT NULL,
    reason_code text NOT NULL,
    justification text NOT NULL,
    evidence jsonb NOT NULL,
    decided_by text NOT NULL,
    decided_at timestamptz NOT NULL,
    supersedes_id text REFERENCES documentary.editorial_decision,
    UNIQUE (corpus_id,revision_id,sequence),
    CHECK ((property='search_enabled' AND unit_id IS NOT NULL AND expected_unit_hash IS NOT NULL)
        OR (property<>'search_enabled' AND unit_id IS NULL AND expected_unit_hash IS NULL))
);
CREATE TABLE documentary.lexical_term_statistics (
    corpus_id text NOT NULL,
    release_id text NOT NULL,
    term text NOT NULL,
    document_frequency bigint NOT NULL CHECK (document_frequency>0),
    PRIMARY KEY (corpus_id,release_id,term),
    FOREIGN KEY (corpus_id,release_id) REFERENCES documentary.release
);
CREATE INDEX document_metadata_gin ON documentary.document USING gin(metadata_vector);
CREATE INDEX unit_text_gin ON documentary.search_unit USING gin(search_vector);
CREATE INDEX editorial_target ON documentary.editorial_decision
    (corpus_id,document_id,unit_id,revision_id,sequence);

-- The phase-1 CLI has no activation/publication operation. Enforce the gate in SQL too.
CREATE FUNCTION documentary.guard_activation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.active_release_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM documentary.release r WHERE r.corpus_id=NEW.corpus_id
        AND r.release_id=NEW.active_release_id AND r.state='ready' AND r.publication_authorized
    ) THEN RAISE EXCEPTION 'Release not ready and authorized for public activation'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER corpus_activation BEFORE INSERT OR UPDATE ON documentary.corpus
    FOR EACH ROW EXECUTE FUNCTION documentary.guard_activation();
