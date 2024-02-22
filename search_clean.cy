MATCH (n:Node) // Adjust 'Node' to your actual node label
UNWIND range(0, size(n.search) - 1) AS i
WITH n, i, n.search[i] AS searchText, n.timestamp[i] AS searchTime
WHERE any(j IN range(0, size(n.search) - 1) WHERE 
    j <> i AND 
    n.search[j] CONTAINS searchText AND 
    abs(n.timestamp[j] - searchTime) <= 60000) // 60,000 milliseconds = 1 minute
WITH n, collect(i) AS indexesToMerge
SET n.search = [index IN range(0, size(n.search) - 1) WHERE NOT index IN indexesToMerge | n.search[index]],
    n.timestamp = [index IN range(0, size(n.timestamp) - 1) WHERE NOT index IN indexesToMerge | n.timestamp[index]]
