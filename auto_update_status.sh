#!/bin/bash

# Auto-update dashboard script
while true; do
    echo "Updating dashboard at $(date)"
    python3 update_status.py
    sleep 60  # Update every minute
done