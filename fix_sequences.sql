-- Script pour corriger les séquences PostgreSQL en production
-- Les séquences doivent être mises à jour pour éviter les conflits d'IDs

-- Corriger la séquence authors_id_seq
SELECT setval('authors_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM authors), false);

-- Corriger la séquence users_id_seq 
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM users), false);

-- Corriger la séquence bookmarks_id_seq
SELECT setval('bookmarks_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM bookmarks), false);

-- Vérifier les valeurs des séquences
SELECT 'authors_id_seq' as sequence_name, last_value, is_called FROM authors_id_seq;
SELECT 'users_id_seq' as sequence_name, last_value, is_called FROM users_id_seq; 
SELECT 'bookmarks_id_seq' as sequence_name, last_value, is_called FROM bookmarks_id_seq;

-- Vérifier les MAX IDs actuels
SELECT 'authors' as table_name, MAX(id) as max_id FROM authors;
SELECT 'users' as table_name, MAX(id) as max_id FROM users;
SELECT 'bookmarks' as table_name, MAX(id) as max_id FROM bookmarks;

SELECT 'Sequences fixed successfully!' as status;