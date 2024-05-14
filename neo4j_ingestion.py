from neo4j import GraphDatabase
import os

# Neo4j database connection details
uri = "bolt://localhost:7687"
user = "neo4j"
password = "your_password"

# Base directory containing .cy files
base_directory_path = "path/to/your/cy/files"

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

# Function to process all .cy files in a given directory and its subdirectories
def process_cy_files_in_directory(session, directory_path):
    outcomes = {}
    for root, dirs, files in os.walk(directory_path):
        for file in sorted(files):
            if file.endswith(".cy"):
                file_path = os.path.join(root, file)
                outcomes[file_path] = execute_cypher_file(session, file_path)
    return outcomes

# Function to process the directories in the required order
def process_directories(session, base_path):
    results = {}

    # Process nodes subdirectories for each datasource
    for datasource in sorted(os.listdir(base_path)):
        nodes_path = os.path.join(base_path, datasource, "nodes")
        if os.path.exists(nodes_path):
            results.update(process_cy_files_in_directory(session, nodes_path))

    # Process edges subdirectories for each datasource
    for datasource in sorted(os.listdir(base_path)):
        edges_path = os.path.join(base_path, datasource, "edges")
        if os.path.exists(edges_path):
            results.update(process_cy_files_in_directory(session, edges_path))

    # Process cleanup directory
    cleanup_path = os.path.join(base_path, "cleanup")
    if os.path.exists(cleanup_path):
        results.update(process_cy_files_in_directory(session, cleanup_path))

    return results

# Create a Neo4j driver instance
driver = GraphDatabase.driver(uri, auth=(user, password))

# Connect to the database and execute queries in the specified order
with driver.session() as session:
    results = process_directories(session, base_directory_path)

# Close the driver connection
driver.close()

# Print the results
for file, outcomes in results.items():
    print(f"{file}: {outcomes}")
