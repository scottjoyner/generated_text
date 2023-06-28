import pandas as pd
import numpy as np

# Suppose we have the following DataFrame:
df = pd.DataFrame({
    'A': ['apple', 'banana', 'cherry', 'banana', 'apple', 'apple', 'cherry'],
    'B': ['fruit', 'fruit', 'fruit', 'fruit', 'fruit', 'fruit', 'fruit'],
    'C': ['red', 'yellow', 'green', 'yellow', 'green', 'red', 'green']
})

# Create a new column 'D' and initialize it with 'FAIL':
df['D'] = 'FAIL'

# List of possible strings to match in column 'C':
list_of_strings = ['red', 'green']

# Get all distinct values in column 'A':
distinct_values = df['A'].unique()

# Iterate over all distinct values:
for value in distinct_values:
    # Create a subset of dataframe:
    subset_df = df[df['A'] == value]
    
    # Check if all values in column 'C' of the subset are in the list of strings:
    if subset_df['C'].isin(list_of_strings).all():
        # If yes, set the value in the new column 'D' to 'PASS' for these rows:
        df.loc[df['A'] == value, 'D'] = 'PASS'

print(df)
