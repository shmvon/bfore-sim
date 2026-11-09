# Seeds: restart from a download

Put a downloaded `fdb.db` here (and optionally `prefs.db`) to restart from it.

At startup the app copies each file into the data folder **only if it is not there yet**. Existing data is never overwritten.

- **Locally:** empty `data/`, put the file here, start the app.
- **On the server:** build the image with the file here; it is copied into an empty volume on the first start. Alternatively, upload `fdb.db` straight into the volume folder while the container is stopped.

Files in this folder are never committed to git (they contain research data), but they are included in the Docker image.
