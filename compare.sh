#!/bin/bash

# Define the directory where the files are located
DIRECTORY="path/to/your/files"

# Get today's and yesterday's dates in YYYYMMDD format
TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d "yesterday" +%Y%m%d)

# Loop through all of today's files in the directory
for TODAY_FILE in "$DIRECTORY"/*"$TODAY"*.csv; do
  # Construct the filename for yesterday's file by replacing today's date with yesterday's
  YESTERDAY_FILE="${TODAY_FILE/$TODAY/$YESTERDAY}"

  # Check if yesterday's file exists
  if [ -f "$YESTERDAY_FILE" ]; then
    # Define the output file for differences
    DIFF_OUTPUT="${TODAY_FILE%.csv}_diff.csv"

    # Sort both files to temporary sorted files
    sort "$TODAY_FILE" > sorted_today.csv
    sort "$YESTERDAY_FILE" > sorted_yesterday.csv

    # Use diff to compare the sorted files, then filter out only the differing lines
    # Ignoring case and leading/trailing whitespace for comparison
    diff --changed-group-format='%>' --unchanged-group-format='' sorted_today.csv sorted_yesterday.csv > "$DIFF_OUTPUT"

    # Optionally, clean up the temporary sorted files
    rm sorted_today.csv sorted_yesterday.csv

    echo "Differences between $TODAY_FILE and $YESTERDAY_FILE have been written to $DIFF_OUTPUT"
  else
    echo "No matching file for $YESTERDAY_FILE found."
  fi
done
