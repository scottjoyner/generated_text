LOAD CSV WITH HEADERS FROM 'file:///path_to_your_file.csv' AS row
MERGE (n:YourLabel {uniqueProperty: row.uniqueProperty})
WITH n, row
OPTIONAL MATCH (n)-[r:PREVIOUS_VERSION]->(old:YourLabel_History)
WITH n, row, old, r
ORDER BY old.version DESC
LIMIT 1
WITH n, row, 
     CASE WHEN old IS NULL OR 
               (old.property1 <> row.csvProperty1 OR 
                old.property2 <> row.csvProperty2 OR 
                ...) 
          THEN true ELSE false END AS hasChanged,
     old
FOREACH(ignoreMe IN CASE WHEN hasChanged AND old IS NOT NULL THEN [1] ELSE [] END |
  REMOVE n:CurrentVersion 
  CREATE (n)-[:PREVIOUS_VERSION {timestamp: timestamp()}]->(old)
)
WITH n, row, hasChanged
SET n.property1 = row.csvProperty1,
    n.property2 = row.csvProperty2,
    ...
SET n:CurrentVersion
