CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE champions(
 name TEXT PRIMARY KEY,
 class TEXT NOT NULL DEFAULT 'Unknown',
 damage_profile TEXT NOT NULL DEFAULT 'Unknown',
 attributes TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE dataset_metadata(
 id TEXT PRIMARY KEY, source TEXT NOT NULL, license TEXT NOT NULL, patch TEXT NOT NULL,
 imported_at TEXT NOT NULL, is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),
 notes TEXT NOT NULL DEFAULT '', sha256 TEXT NOT NULL,
 UNIQUE(source,license,patch,sha256)
);
CREATE TABLE champion_roles(
 dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
 name TEXT NOT NULL REFERENCES champions(name),
 role TEXT NOT NULL CHECK(role IN ('Top','Jungle','Mid','ADC','Support')),
 PRIMARY KEY(dataset_id,name,role)
);
CREATE TABLE champion_stats(
 dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
 name TEXT NOT NULL REFERENCES champions(name), role TEXT NOT NULL CHECK(role IN ('Top','Jungle','Mid','ADC','Support')),
 patch TEXT NOT NULL, rank TEXT NOT NULL, region TEXT NOT NULL,
 wins INTEGER NOT NULL CHECK(typeof(wins)='integer' AND wins >= 0),
 games INTEGER NOT NULL CHECK(typeof(games)='integer' AND games >= wins AND games > 0),
 PRIMARY KEY(dataset_id,name,role,patch,rank,region)
);
CREATE TABLE matchup_stats(
 dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
 name TEXT NOT NULL REFERENCES champions(name), opponent TEXT NOT NULL REFERENCES champions(name),
 role TEXT NOT NULL CHECK(role IN ('Top','Jungle','Mid','ADC','Support')),
 opponent_role TEXT NOT NULL CHECK(opponent_role IN ('Top','Jungle','Mid','ADC','Support')),
 patch TEXT NOT NULL, rank TEXT NOT NULL, region TEXT NOT NULL,
 wins INTEGER NOT NULL CHECK(typeof(wins)='integer' AND wins >= 0),
 games INTEGER NOT NULL CHECK(typeof(games)='integer' AND games >= wins AND games > 0),
 CHECK(name <> opponent),
 PRIMARY KEY(dataset_id,name,opponent,role,opponent_role,patch,rank,region)
);
CREATE TABLE synergy_stats(
 dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
 name TEXT NOT NULL REFERENCES champions(name), ally TEXT NOT NULL REFERENCES champions(name),
 role TEXT NOT NULL CHECK(role IN ('Top','Jungle','Mid','ADC','Support')),
 ally_role TEXT NOT NULL CHECK(ally_role IN ('Top','Jungle','Mid','ADC','Support')),
 patch TEXT NOT NULL, rank TEXT NOT NULL, region TEXT NOT NULL,
 wins INTEGER NOT NULL CHECK(typeof(wins)='integer' AND wins >= 0),
 games INTEGER NOT NULL CHECK(typeof(games)='integer' AND games >= wins AND games > 0),
 CHECK(name <> ally AND role <> ally_role),
 PRIMARY KEY(dataset_id,name,ally,role,ally_role,patch,rank,region)
);
CREATE INDEX baseline_filter ON champion_stats(dataset_id,patch,rank,region,role);
CREATE INDEX matchup_filter ON matchup_stats(dataset_id,patch,rank,region,role);
CREATE INDEX synergy_filter ON synergy_stats(dataset_id,patch,rank,region,role);
