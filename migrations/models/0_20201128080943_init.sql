##### upgrade #####
CREATE TABLE IF NOT EXISTS "globalsettings" (
    "id" SMALLINT NOT NULL  PRIMARY KEY DEFAULT 0,
    "default_prefix" TEXT NOT NULL,
    "default_verbosity" BOOL NOT NULL
);
CREATE TABLE IF NOT EXISTS "guild" (
    "id" BIGINT NOT NULL  PRIMARY KEY,
    "delete_at" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "banutilbanevent" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "message_id" BIGINT NOT NULL,
    "message_channel" BIGINT NOT NULL,
    "target_id" BIGINT NOT NULL,
    "banner_id" BIGINT,
    "ban_reason" TEXT NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "banned" BOOL NOT NULL  DEFAULT True,
    "reported" TIMESTAMPTZ,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "banutilcrossbanevent" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "message_id" BIGINT NOT NULL,
    "message_channel" BIGINT NOT NULL,
    "banned" BOOL NOT NULL  DEFAULT False,
    "reported" TIMESTAMPTZ,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE,
    "event_id" INT NOT NULL REFERENCES "banutilbanevent" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "banutilinvite" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "to_guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE,
    "from_guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "banutilsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "enabled" BOOL NOT NULL  DEFAULT False,
    "foreign_log_channel" BIGINT,
    "domestic_log_channel" BIGINT,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "banutilsubscription" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "to_guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE,
    "from_guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "guildsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "prefix" TEXT,
    "verbosity" BOOL,
    "auth_role" BIGINT,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "previewfilter" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "channel_id" BIGINT NOT NULL,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "previewsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "enabled" BOOL NOT NULL  DEFAULT False,
    "log_channel" BIGINT,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "wordwatchignore" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "target_id" BIGINT NOT NULL,
    "mention_type" VARCHAR(2) NOT NULL,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "wordwatchpinggroup" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "wordwatchping" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "ping_type" VARCHAR(2) NOT NULL,
    "target_id" BIGINT NOT NULL,
    "group_id" INT NOT NULL REFERENCES "wordwatchpinggroup" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "wordwatchsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "enabled" BOOL NOT NULL  DEFAULT False,
    "log_channel" BIGINT,
    "header" TEXT,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "wordwatchwatch" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "pattern" TEXT NOT NULL,
    "match_type" INT NOT NULL,
    "auto_delete" BOOL NOT NULL,
    "ignore_case" BOOL NOT NULL,
    "group_id" INT REFERENCES "wordwatchpinggroup" ("id") ON DELETE SET NULL,
    "guild_id" BIGINT NOT NULL REFERENCES "guild" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL
);;
