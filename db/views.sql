CREATE SOURCE wikirecent
FROM FILE '/tmp/wikirecent' WITH (tail = true)
FORMAT REGEX '^data: (?P<data>.*)';

CREATE MATERIALIZED VIEW recentchanges AS
    SELECT
        val->>'$schema' AS r_schema,
        (val->'bot')::bool AS bot,
        val->>'comment' AS comment,
        (val->'id')::float::int AS id,
        (val->'length'->'new')::float::int AS length_new,
        (val->'length'->'old')::float::int AS length_old,
        val->'meta'->>'uri' AS meta_uri,
        val->'meta'->>'id' as meta_id,
        (val->'minor')::bool AS minor,
        (val->'namespace')::float AS namespace,
        val->>'parsedcomment' AS parsedcomment,
        (val->'revision'->'new')::float::int AS revision_new,
        (val->'revision'->'old')::float::int AS revision_old,
        val->>'server_name' AS server_name,
        (val->'server_script_path')::text AS server_script_path,
        val->>'server_url' AS server_url,
        (val->'timestamp')::float AS r_ts,
        val->>'title' AS title,
        val->>'type' AS type,
        val->>'user' AS user,
        val->>'wiki' AS wiki
    FROM (SELECT data::jsonb AS val FROM wikirecent);

CREATE MATERIALIZED VIEW counter AS
    SELECT COUNT(*) FROM recentchanges;

CREATE MATERIALIZED VIEW user_edits AS
    SELECT user, count(*) FROM recentchanges GROUP BY user;

CREATE MATERIALIZED VIEW top_users AS
    SELECT * FROM user_edits ORDER BY count DESC LIMIT 10;

CREATE MATERIALIZED VIEW server_edits AS
    SELECT server_name, count(*) FROM recentchanges GROUP BY server_name;

CREATE MATERIALIZED VIEW top_servers AS
    SELECT * FROM server_edits ORDER BY count DESC LIMIT 10;

CREATE MATERIALIZED VIEW page_edits AS
    SELECT title, count(*) FROM recentchanges GROUP BY title;

CREATE MATERIALIZED VIEW top_pages AS
    SELECT * FROM page_edits ORDER BY count DESC LIMIT 10;
