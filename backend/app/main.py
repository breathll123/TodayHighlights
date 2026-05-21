from fastapi import FastAPI

from app.api import admin, public

app = FastAPI(title="Daily Highlights API")
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
