-- LuomiNest PostgreSQL Initialization
-- Enable pgvector extension for vector memory support.
CREATE EXTENSION IF NOT EXISTS vector;

-- Create application user if it does not match the default superuser.
-- The default docker-compose mounts this file; adjust as needed.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'luominest_app') THEN
        CREATE ROLE luominest_app WITH LOGIN PASSWORD 'luominest_app';
    END IF;
END
$$;

-- Grant privileges on the application database.
GRANT ALL PRIVILEGES ON DATABASE luominest TO luominest_app;
