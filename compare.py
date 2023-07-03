import pandas as pd

# sample data
data = {
    'Column1': ['Hello world', 'OpenAI is great', 'GPT-4 is amazing'],
    'Column2': ['Hello earth', 'OpenAI is awesome', 'GPT-4 is superb']
}

df = pd.DataFrame(data)

# function to compare two strings
def compare_strings(str1, str2):
    str1_words = set(str1.split())
    str2_words = set(str2.split())

    common_words = str1_words & str2_words
    different_words = (str1_words | str2_words) - common_words

    return ', '.join(different_words)

# create a new column for the differences
df['Differences'] = df.apply(lambda row: compare_strings(row['Column1'], row['Column2']), axis=1)

print(df)
