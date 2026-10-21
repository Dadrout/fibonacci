#!/bin/bash
# Setup cron job for automatic file cleanup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_old_files.py"

echo "Setting up automatic cleanup cron job..."

# Make cleanup script executable
chmod +x "$CLEANUP_SCRIPT"

# Add cron job to run cleanup daily at 2 AM
CRON_JOB="0 2 * * * cd $SCRIPT_DIR && /usr/bin/python3 $CLEANUP_SCRIPT >> /var/log/wizetale_cleanup.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$CLEANUP_SCRIPT"; then
    echo "Cleanup cron job already exists"
else
    # Add the cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "Added cleanup cron job: runs daily at 2 AM"
fi

echo "Current crontab:"
crontab -l

echo "Setup complete!"
echo "Cleanup will run daily at 2 AM and log to /var/log/wizetale_cleanup.log" 