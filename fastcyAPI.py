from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from bson import ObjectId
from typing import List

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
        return graph
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
    new_graph_id = graphs.insert_one(graph_data).inserted_id
    return {"graph_id": str(new_graph_id)}
