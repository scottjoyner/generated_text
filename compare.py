import os
import gzip
import pandas as pd
from datetime import datetime, timedelta

directory = "path/to/your/files"
today = datetime.today().strftime("%Y%m%d")
yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")

for filename in os.listdir(directory):
    if filename.endswith(f"{today}.csv.gz"):
        yesterday_filename = filename.replace(today, yesterday)
        yesterday_file_path = os.path.join(directory, yesterday_filename)

        if os.path.isfile(yesterday_file_path):
            diff_output = os.path.join(directory, f"{filename}_diff.csv")

            today_df = pd.read_csv(os.path.join(directory, filename), compression='gzip')
            yesterday_df = pd.read_csv(yesterday_file_path, compression='gzip')
            diff_df = today_df.merge(yesterday_df, indicator=True, how='outer').loc[lambda x: x['_merge'] != 'both']

            diff_df.to_csv(diff_output, index=False)
            print(f"Differences between {filename} and {yesterday_filename} have been written to {diff_output}")
        else:
            print(f"No matching file for {yesterday_filename} found.")
