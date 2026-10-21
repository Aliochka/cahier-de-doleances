-- Read-only monitoring, separate administrator session, never resets counters.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SELECT pid,datname,application_name,state,wait_event_type,wait_event
FROM pg_stat_activity WHERE datname='cahier_search';
SELECT pid,phase,blocks_done,blocks_total,tuples_done,tuples_total
FROM pg_stat_progress_create_index WHERE datname='cahier_search';
SELECT pg_database_size('cahier_search') AS database_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(),'0/0') AS wal_position_bytes;
SELECT wal_bytes FROM pg_stat_wal;
SELECT datname,temp_files,temp_bytes FROM pg_stat_database WHERE datname='cahier_search';
COMMIT;
