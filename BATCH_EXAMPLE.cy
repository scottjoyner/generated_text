// Parameters are provided from the CSV. Assume params are {id, name, email}
WITH $id AS nodeId, $name AS newName, $email AS newEmail
MATCH (current:Node:Current {id: nodeId}) // Match the current node

// Check if any fields have changed
WHERE current.name <> newName OR current.email <> newEmail
WITH current, newName, newEmail

// Mark the current node as Historical and remove Current label
REMOVE current:Current
SET current:Historical

// Create a new version of the node with Current label
CREATE (newNode:Node:Current {name: newName, email: newEmail, createdAt: timestamp()})

// Add the :PREVIOUS_VERSION relationship from the new node to the current
CREATE (newNode)-[:PREVIOUS_VERSION {from: timestamp()}]->(current)

// Transfer relationships from the current to the new node, setting new timestamps
WITH current, newNode
MATCH (current)-[rel]->(other) // Assume we need to replicate all outgoing relationships
WHERE NOT type(rel) = 'PREVIOUS_VERSION' // Avoid versioning relationships themselves

// Clone the relationship from current to newNode
FOREACH (ignoreMe IN CASE WHEN type(rel) = 'RELTYPE' THEN [1] ELSE [] END |
    CREATE (newNode)-[newRel:RELTYPE {from: timestamp()}]->(other)
    SET newRel = properties(rel)
    REMOVE newRel.from, newRel.to // Remove irrelevant properties if any
)

RETURN newNode
