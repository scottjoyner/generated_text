from neo4j import GraphDatabase
import os

# Neo4j database connection details
uri = "bolt://localhost:7687"
user = "neo4j"
password = "your_password"

# Directory containing .cy files
directory_path = "path/to/your/cy/files"

# Function to execute Cypher queries from a file and return the outcome
def execute_cypher_file(session, file_path):
    with open(file_path, 'r') as file:
        cypher_queries = file.read().strip()
        queries = cypher_queries.split(';')
        outcomes = []
        for query in queries:
            if query.strip():
                result = session.run(query.strip())
                summary = result.consume()
                outcomes.append(summary.counters.nodes_created)
        return outcomes

# Create a Neo4j driver instance
driver = GraphDatabase.driver(uri, auth=(user, password))

# Connect to the database and execute queries from each .cy file
results = {}
with driver.session() as session:
    for filename in os.listdir(directory_path):
        if filename.endswith(".cy"):
            file_path = os.path.join(directory_path, filename)
            outcomes = execute_cypher_file(session, file_path)
            results[filename] = outcomes

# Close the driver connection
driver.close()

# Print the results
for file, outcomes in results.items():
    print(f"{file}: {outcomes}")
