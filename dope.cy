MATCH (a:Label {identifier: 'value1'}), (b:Label {identifier: 'value2'})
WITH a, b, PROPERTIES(a) AS propsA, PROPERTIES(b) AS propsB
RETURN a, b,
       [k IN KEYS(propsA) WHERE propsA[k] <> propsB[k] | k] AS differingProperties
