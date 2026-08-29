-- Create Temporal databases on the shared Postgres instance.
CREATE DATABASE temporal;
CREATE DATABASE temporal_visibility;
GRANT ALL PRIVILEGES ON DATABASE temporal TO agentsuite;
GRANT ALL PRIVILEGES ON DATABASE temporal_visibility TO agentsuite;
