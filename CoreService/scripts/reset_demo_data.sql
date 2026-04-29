-- Reset Magellon import data
-- Wipes msession / image / image_job / image_job_task / image_meta_data / job_event
-- Keeps security, lookup tables, projects, plugins, pipelines, atlas, sample_material.
--
-- Usage:
--   mysql -u root -p magellon01 < scripts/reset_demo_data.sql
--
-- Or from a mysql shell already connected to the DB:
--   SOURCE scripts/reset_demo_data.sql;

USE magellon01;

SET FOREIGN_KEY_CHECKS = 0;

-- Children first (matches FK order in models/sqlalchemy_models.py).
TRUNCATE TABLE job_event;
TRUNCATE TABLE image_meta_data;
TRUNCATE TABLE image_job_task;
TRUNCATE TABLE image_job;
TRUNCATE TABLE image;
TRUNCATE TABLE msession;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'job_event'       AS table_name, COUNT(*) AS row_count FROM job_event
UNION ALL SELECT 'image_meta_data', COUNT(*) FROM image_meta_data
UNION ALL SELECT 'image_job_task', COUNT(*) FROM image_job_task
UNION ALL SELECT 'image_job',      COUNT(*) FROM image_job
UNION ALL SELECT 'image',          COUNT(*) FROM image
UNION ALL SELECT 'msession',       COUNT(*) FROM msession;
