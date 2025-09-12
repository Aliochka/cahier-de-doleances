-- Script pour créer les tables manquantes en production
-- Tables users et bookmarks + liaison avec authors

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    nationalities TEXT, -- JSON array des codes pays ISO
    profile_completed BOOLEAN DEFAULT false,
    author_id BIGINT REFERENCES authors(id)
);

-- Index pour l'email (recherche fréquente)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Table des marques-pages
CREATE TABLE IF NOT EXISTS bookmarks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    page_type VARCHAR(50) NOT NULL, -- 'question', 'answer', 'author'  
    page_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Contrainte d'unicité : un utilisateur ne peut pas avoir le même marque-page deux fois
    CONSTRAINT unique_user_bookmark UNIQUE (user_id, page_type, page_id)
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_type ON bookmarks(user_id, page_type);

-- Ajouter les colonnes manquantes à la table authors si elles n'existent pas
ALTER TABLE authors ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id);
ALTER TABLE authors ADD COLUMN IF NOT EXISTS is_anonymous BOOLEAN DEFAULT true;

-- Mise à jour de la table alembic_version pour refléter l'état actuel
INSERT INTO alembic_version (version_num) VALUES ('bb11df9341ed') 
ON CONFLICT (version_num) DO NOTHING;