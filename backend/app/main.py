from fastapi import FastAPI

app = FastAPI(title="Daily Highlights API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
