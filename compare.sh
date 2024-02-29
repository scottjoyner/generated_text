#!/bin/bash

# Define the directory where the files are located
DIRECTORY="path/to/your/files"

# Get today's and yesterday's dates in YYYYMMDD format
TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d "yesterday" +%Y%m%d)

# Loop through all of today's compressed CSV files in the directory
for TODAY_FILE_GZ in "$DIRECTORY"/*"$TODAY"*.csv.gz; do
  # Construct the filename for yesterday's file by replacing today's date with yesterday's
  YESTERDAY_FILE_GZ="${TODAY_FILE_GZ/$TODAY/$YESTERDAY}"

  # Check if yesterday's compressed file exists
  if [ -f "$YESTERDAY_FILE_GZ" ]; then
    # Define the output file for differences
    DIFF_OUTPUT="${TODAY_FILE_GZ%.csv.gz}_diff.csv"

    # Use zcat to decompress and sort both files to temporary sorted files
    zcat "$TODAY_FILE_GZ" | sort > sorted_today.csv
    zcat "$YESTERDAY_FILE_GZ" | sort > sorted_yesterday.csv

    # Use diff to compare the sorted files, then filter out only the differing lines
    # Ignoring case and leading/trailing whitespace for comparison
    diff --changed-group-format='%>' --unchanged-group-format='' sorted_today.csv sorted_yesterday.csv > "$DIFF_OUTPUT"

    # Optionally, clean up the temporary sorted files
    rm sorted_today.csv sorted_yesterday.csv

    echo "Differences between $TODAY_FILE_GZ and $YESTERDAY_FILE_GZ have been written to $DIFF_OUTPUT"
  else
    echo "No matching file for $YESTERDAY_FILE_GZ found."
  fi
done
