CREATE TABLE dataset_champions(
 dataset_id TEXT NOT NULL REFERENCES dataset_metadata(id) ON DELETE CASCADE,
 name TEXT NOT NULL REFERENCES champions(name),
 class TEXT NOT NULL,
 damage_profile TEXT NOT NULL,
 attributes TEXT NOT NULL,
 PRIMARY KEY(dataset_id,name)
);
INSERT INTO dataset_champions(dataset_id,name,class,damage_profile,attributes)
SELECT d.id,c.name,c.class,c.damage_profile,c.attributes FROM dataset_metadata d CROSS JOIN champions c;
