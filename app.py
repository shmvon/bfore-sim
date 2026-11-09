#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  7 13:58:16 2023

@author: semvandekerckhove
"""

import threading
from flask import Flask

import config
import i18n
from website import website
from cleanup import run_cleanup

app = Flask(__name__)

# Restore a downloaded fdb.db from seeds/ into an empty data folder (never overwrites)
config.seed_data_dir()

app.secret_key = config.secret_key()

# Register the website blueprint and the translations
app.register_blueprint(website)
i18n.init_app(app)

# Show where the data is stored (check this in the server log)
config.report()

# Always start cleanup thread
cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
cleanup_thread.start()

# the server administrator requests that your application listens on all interfaces
if __name__ == "__main__":
    # Run the Flask application. Port 5000 is often taken on macOS (AirPlay),
    # so the default is 8500; the Docker image sets PORT=5000 for the server.
    # Debug mode (auto-reload, interactive debugger) only locally, never on the server.
    app.run(host='::', port=config.PORT, debug=not config._in_container())
