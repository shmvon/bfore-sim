import os
import time

from config import DATA_DIR


def delete_old_databases():
    current_time = time.time()
    for file in os.listdir(DATA_DIR):
        if file.endswith("-user.db"):
            path = os.path.join(DATA_DIR, file)
            # Delete the database file if it's older than three hours (10800 seconds)
            if current_time - os.path.getmtime(path) > 10800:
                print(f"Deleting file: {file}")
                os.remove(path)


def run_cleanup():
    while True:
        print("Running cleanup...")
        delete_old_databases()
        time.sleep(600)  # Wait for 10 minutes before checking again
