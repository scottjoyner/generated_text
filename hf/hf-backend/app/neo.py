from neo4j import GraphDatabase
from .config import settings

driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

CONSTRAINTS = [
    "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT model_id IF NOT EXISTS FOR (m:Model) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT license_name IF NOT EXISTS FOR (l:License) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT pipeline_name IF NOT EXISTS FOR (p:Pipeline) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT space_name IF NOT EXISTS FOR (s:Space) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT file_name IF NOT EXISTS FOR (f:File) REQUIRE f.name IS UNIQUE",
    "CREATE CONSTRAINT lib_name IF NOT EXISTS FOR (l:Library) REQUIRE l.name IS UNIQUE"
]

FULLTEXT = [
    "CALL db.index.fulltext.createNodeIndex('modelText', ['Model'], ['id','name','card_summary'])",
    "CALL db.index.fulltext.createNodeIndex('tagText', ['Tag'], ['name'])"
]

def ensure_schema():
    with driver.session() as sess:
        for q in CONSTRAINTS:
            sess.run(q)
        # Best-effort create fulltext (ignore if exists)
        for q in FULLTEXT:
            try:
                sess.run(q)
            except Exception:
                pass

def close():
    driver.close()
