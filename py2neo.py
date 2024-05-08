from flask import Flask, request, jsonify
from py2neo import Graph, Node, Relationship

app = Flask(__name__)

# Connect to the Neo4j database
graph = Graph("bolt://localhost:7687", auth=("neo4j", "password"))

@app.route('/api', methods=['POST'])
def handle_location_data():
    data = request.get_json()
    # Create a new node for the location data
    location_node = Node("Location", data=data)
    graph.create(location_node)
    
    # Create a relationship to a previous location node (if it exists)
    previous_node = graph.find_one("Location", "data.timestamp < {ts}".format(ts=data["timestamp"]))
    if previous_node:
        rel = Relationship(location_node, "FOLLOWED_BY", previous_node)
        graph.create(rel)
    
    return jsonify({"result": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
