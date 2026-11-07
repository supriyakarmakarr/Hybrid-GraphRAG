-- Local Compose demo accounts only; this file is not part of the hosted database migration.
INSERT INTO users (user_id, tenant_id, username, email, roles)
VALUES
  ('dev-admin-001', 'tenant-dev', 'admin', 'admin@dev.local', ARRAY['admin','analyst']),
  ('dev-intern-001', 'tenant-dev', 'intern', 'intern@dev.local', ARRAY['intern'])
ON CONFLICT DO NOTHING;
