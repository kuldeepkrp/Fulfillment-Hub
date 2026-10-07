# Streamlit Community Cloud Deployment

1. Push this entire project folder to a GitHub repository.
2. Keep `app.py` and `requirements.txt` in the repository root.
3. Go to `https://share.streamlit.io/` and sign in with GitHub.
4. Click **Create app** and choose the GitHub repository, branch, and `app.py` as the entrypoint.
5. Deploy and wait for the build to finish.
6. Share the generated `streamlit.app` URL in the assessment submission.

The SQLite file `fulfillment_hub.db` is included in the repository so the demo has sample data on first launch.

Important: this project is a take-home demonstration using local SQLite sample data. It is not designed as a multi-user production system with persistent writes across cloud redeployments.
