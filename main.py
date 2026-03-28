import uvicorn

# This tells uvicorn to look inside the 'app' FOLDER, 
# then the 'main.py' FILE, for the 'app' VARIABLE.
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)