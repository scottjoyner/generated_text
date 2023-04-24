MATCH (n)-[:LINKED_TO*]->(m)
WITH n, m, [(n)-[:LINKED_TO*]->(x) | x.value] AS values
WITH n, m, values, size(values) as chain_length, [i IN range(0, chain_length - 2) | abs(values[i] - values[i + 1])] as differences
WITH n, m, reduce(total = 0, d in differences | total + d) as total_difference
RETURN n, m, total_difference / (CASE WHEN chain_length > 1 THEN chain_length - 1 ELSE 1 END) as average_difference
