# Keep `pytest` (run at the repo root) from collecting the standalone evidence
# scripts under reports/ — they are run directly, not as pytest tests, and call
# sys.exit(), which would abort collection.
collect_ignore_glob = ["reports/*"]
