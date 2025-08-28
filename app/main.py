from fastapi import FastAPI

app = FastAPI(title="Study Helper Pro", version="0.1.0")

@app.get("/")
async def read_root():
    return {"message": "Hello World"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}