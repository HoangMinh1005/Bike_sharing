from fastapi import FastAPI

app = FastAPI(title="Bike Sharing API")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Bike Sharing Operation Intelligence API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
