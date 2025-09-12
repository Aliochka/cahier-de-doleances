-- Script pour nettoyer et créer les tables manquantes en production
-- À exécuter avec : psql <DATABASE_URL> < fix_production_schema.sql

-- 1. Nettoyer les séquences orphelines si elles existent
DROP SEQUENCE IF EXISTS users_id_seq CASCADE;
DROP SEQUENCE IF EXISTS bookmarks_id_seq CASCADE;

-- 2. Supprimer les tables si elles existent (par précaution)
DROP TABLE IF EXISTS bookmarks CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 3. Créer la table users
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_login TIMESTAMPTZ,
    nationalities TEXT, -- JSON array des codes pays ISO
    profile_completed BOOLEAN DEFAULT false NOT NULL,
    author_id BIGINT REFERENCES authors(id)
);

-- 4. Index pour l'email (recherche fréquente)
CREATE INDEX idx_users_email ON users(email);

-- 5. Créer la table bookmarks
CREATE TABLE bookmarks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    page_type VARCHAR(50) NOT NULL, -- 'question', 'answer', 'author'  
    page_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Contrainte d'unicité : un utilisateur ne peut pas avoir le même marque-page deux fois
    CONSTRAINT unique_user_bookmark UNIQUE (user_id, page_type, page_id)
);

-- 6. Index pour les requêtes fréquentes
CREATE INDEX idx_bookmarks_user_type ON bookmarks(user_id, page_type);

-- 7. Ajouter les colonnes manquantes à la table authors
-- Vérifier d'abord si les colonnes existent déjà
DO $$ 
BEGIN
    -- Ajouter user_id si elle n'existe pas
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'authors' AND column_name = 'user_id') THEN
        ALTER TABLE authors ADD COLUMN user_id BIGINT REFERENCES users(id);
    END IF;
    
    -- Ajouter is_anonymous si elle n'existe pas  
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'authors' AND column_name = 'is_anonymous') THEN
        ALTER TABLE authors ADD COLUMN is_anonymous BOOLEAN DEFAULT true;
    END IF;
END $$;

-- 8. Mettre à jour la version Alembic
UPDATE alembic_version SET version_num = 'bb11df9341ed';

-- 9. Vérifier les tables créées
\d users
\d bookmarks
\d authors

-- 10. Afficher le statut final
SELECT 'Schema setup completed successfully!' as status;