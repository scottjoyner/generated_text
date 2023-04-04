from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from bson import ObjectId
from typing import List
import networkx as nx
from py2cytoscape.data.cynetwork import CyNetwork
from py2cytoscape.data.cyrest_client import CyRestClient

app = FastAPI()

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["mydatabase"]
graphs = db["graphs"]

# Endpoint to retrieve graph by ID
@app.get("/graph/{graph_id}")
async def get_graph(graph_id: str):
    graph = graphs.find_one({"_id": ObjectId(graph_id)})
    if graph:
        # Convert the graph data to a NetworkX graph
        nx_graph = nx.Graph(graph)
        # Convert the NetworkX graph to a Cytoscape graph
        cy_network = CyNetwork()
        cy_network.from_networkx(nx_graph)
        # Return the Cytoscape graph data
        return cy_network.to_json()
    else:
        raise HTTPException(status_code=404, detail="Graph not found")

# Endpoint to retrieve all node types
@app.get("/nodetype")
async def get_node_types():
    node_types = []
    for graph in graphs.find():
        for node in graph["nodes"]:
            if node["type"] not in node_types:
                node_types.append(node["type"])
    return node_types

# Endpoint to retrieve all edge types
@app.get("/edgetype")
async def get_edge_types():
    edge_types = []
    for graph in graphs.find():
        for edge in graph["edges"]:
            if edge["type"] not in edge_types:
                edge_types.append(edge["type"])
    return edge_types

# Endpoint to save current graph as a new document
@app.post("/savegraph")
async def save_graph():
    # Format graph data here
    # Convert the graph data to a NetworkX graph
    nx_graph = nx.Graph(graph_data)
    # Convert the NetworkX graph to a Cytoscape graph
    cy_network = CyNetwork()
    cy_network.from_networkx(nx_graph)
    # Save the Cytoscape graph data to MongoDB
    new_graph_id = graphs.insert_one(cy_network.to_json()).inserted_id
    return {"graph_id": str(new_graph_id)}
