"""
RecommendMe API — root entry point.

Run the development server with:
    uvicorn app.main:app --reload

Or execute this file directly:
    python main.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
