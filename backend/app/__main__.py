"""python -m app: run the API on port 8008."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8008, reload=True)
