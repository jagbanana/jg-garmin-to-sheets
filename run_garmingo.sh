#!/bin/bash
cd /Users/$USER/jg-garmin-to-sheets-main

# Run for USER1
/Users/$USER/jg-garmin-to-sheets-main/venv/bin/python3 -m src.main \
  --profile USER1 \
  --output-type sheets \
  --resume \
  --end-offset 1

# Run for USER2
/Users/$USER/jg-garmin-to-sheets-main/venv/bin/python3 -m src.main \
  --profile USER2 \
  --output-type sheets \
  --resume \
  --end-offset 1