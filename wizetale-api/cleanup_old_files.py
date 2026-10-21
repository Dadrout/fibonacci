#!/usr/bin/env python3
"""
Cleanup script for removing old generated files.
Removes files older than specified days from generated directories.
"""

import os
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
DAYS_TO_KEEP = 7  # Keep files for 7 days
DIRECTORIES_TO_CLEAN = [
    "generated_videos",
    "generated_audio", 
    "generated_images",
    "static"  # User generated files in static/{user_id}/
]

def clean_old_files(directory: Path, days_to_keep: int):
    """Remove files older than specified days from directory."""
    if not directory.exists():
        print(f"Directory {directory} does not exist, skipping...")
        return 0, 0
    
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    cleaned_count = 0
    cleaned_size = 0
    
    print(f"Cleaning files older than {days_to_keep} days from {directory}")
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            try:
                # Get file modification time
                file_mtime = file_path.stat().st_mtime
                
                if file_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    file_age_days = (time.time() - file_mtime) / (24 * 60 * 60)
                    
                    print(f"  Removing {file_path} (age: {file_age_days:.1f} days, size: {file_size/1024/1024:.1f} MB)")
                    file_path.unlink()
                    cleaned_count += 1
                    cleaned_size += file_size
                    
            except Exception as e:
                print(f"  Error processing {file_path}: {e}")
        
        # Remove empty directories (but keep main directories)
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if dir_path != directory and dir_path.is_dir():
                    # Check if directory is empty
                    if not any(dir_path.iterdir()):
                        print(f"  Removing empty directory {dir_path}")
                        dir_path.rmdir()
            except Exception as e:
                print(f"  Error removing directory {dir_path}: {e}")
    
    if cleaned_count > 0:
        print(f"  Cleaned {cleaned_count} files, freed {cleaned_size/1024/1024:.1f} MB")
    else:
        print(f"  No files to clean")
    
    return cleaned_count, cleaned_size

def main():
    """Main cleanup function."""
    print(f"Starting cleanup at {datetime.now()}")
    print(f"Keeping files newer than {DAYS_TO_KEEP} days")
    
    total_cleaned = 0
    total_size_freed = 0
    
    # Get the script directory (should be in wizetale-api/)
    script_dir = Path(__file__).parent
    
    for dir_name in DIRECTORIES_TO_CLEAN:
        dir_path = script_dir / dir_name
        count, size = clean_old_files(dir_path, DAYS_TO_KEEP)
        total_cleaned += count
        total_size_freed += size
    
    print(f"\nCleanup completed at {datetime.now()}")
    print(f"Total files cleaned: {total_cleaned}")
    print(f"Total space freed: {total_size_freed/1024/1024:.1f} MB")

if __name__ == "__main__":
    main() 