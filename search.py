# Keyword Frequency:

def rank_by_keyword_frequency(query, items):
    ranked_items = []
    for item in items:
        title_count = item[0].count(query)
        description_count = item[1].count(query)
        total_count = title_count + description_count
        ranked_items.append((item, total_count))
    ranked_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in ranked_items]
  
  
# Keyword Proximity:

def rank_by_keyword_proximity(query, items):
    ranked_items = []
    for item in items:
        title_distance = item[0].lower().find(query.lower())
        description_distance = item[1].lower().find(query.lower())
        total_distance = min(title_distance, description_distance)
        ranked_items.append((item, total_distance))
    ranked_items.sort(key=lambda x: x[1])
    return [item[0] for item in ranked_items]

# TF-IDF:

import math
from collections import Counter

def rank_by_tfidf(query, items):
    ranked_items = []
    query_words = query.lower().split()
    word_counts = Counter([word for item in items for word in item[0].lower().split() + item[1].lower().split()])
    num_items = len(items)
    for item in items:
        tfidf_sum = 0
        for word in query_words:
            tf = 0.5 + 0.5 * (item[0].lower().count(word) + item[1].lower().count(word)) / (len(item[0]) + len(item[1]))
            idf = math.log(num_items / word_counts[word])
            tfidf_sum += tf * idf
        ranked_items.append((item, tfidf_sum))
    ranked_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in ranked_items]

# PageRank:

import networkx as nx

def rank_by_pagerank(query, items):
    item_titles = [item[0] for item in items]
    graph = nx.DiGraph()
    for i, title1 in enumerate(item_titles):
        for j, title2 in enumerate(item_titles):
            if i != j:
                weight = len(set(title1.lower().split()) & set(title2.lower().split())) + len(set(title1.lower().split()) & set(items[j][1].lower().split())) + len(set(title2.lower().split()) & set(items[i][1].lower().split()))
                if weight > 0:
                    graph.add_edge(title1, title2, weight=weight)
    pageranks = nx.pagerank_numpy(graph)
    ranked_items = [(items[item_titles.index(title)], pageranks[title]) for title in pageranks.keys()]
    ranked_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in ranked_items]

  
