"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="FlowGuard",
    description="Configurable workflow decision platform",
    version="0.1.0",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Return the process health status."""
    return {"status": "ok"}
