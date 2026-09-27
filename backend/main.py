from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if __package__:
    from .api.schemas import IngestResponse, SessionIngest
else:
    from api.schemas import IngestResponse, SessionIngest


app = FastAPI(title="SmartWear AI Backend Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/sessions/ingest", response_model=IngestResponse)
async def ingest_session(payload: SessionIngest):
    return {
        "status": "success",
        "session_id": payload.session_id,
        "message": "Contract validated successfully",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)