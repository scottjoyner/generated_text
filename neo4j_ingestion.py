from neo4j import GraphDatabase
import os

# Neo4j database connection details
uri = "bolt://localhost:7687"
user = "neo4j"
password = "your_password"

# Directory containing .cy files
directory_path = "path/to/your/cy/files"

# Function to execute Cypher queries from a file
def execute_cypher_file(session, file_path):
    with open(file_path, 'r') as file:
        cypher_queries = file.read().strip()
        queries = cypher_queries.split(';')
        for query in queries:
            if query.strip():
                session.run(query.strip())

# Create a Neo4j driver instance
driver = GraphDatabase.driver(uri, auth=(user, password))

# Connect to the database and execute queries from each .cy file
with driver.session() as session:
    for filename in os.listdir(directory_path):
        if filename.endswith(".cy"):
            file_path = os.path.join(directory_path, filename)
            execute_cypher_file(session, file_path)

# Close the driver connection
driver.close()
