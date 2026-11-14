import logging
import os

from fastapi import FastAPI, HTTPException

from src.api.models import QueryRequest, RegimeResponse
from src.orchestrator.engine import BlueprintError, Orchestrator
from src.router.mock_router import MockSemanticRouter

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Quant Library Orchestrator",
    description="Deterministic Quantitative Routing API",
    version="1.0.0",
)

# dependency injection (simplified)
router = MockSemanticRouter()
orchestrator = Orchestrator(router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# A plain `def`, not `async def`: the work is CPU-bound, so FastAPI runs it in its thread pool
# instead of blocking the event loop.
@app.post("/query", response_model=RegimeResponse)
def query_endpoint(request: QueryRequest):
    """
    Process a natural language query to generate a quantitative regime.
    """
    try:
        if request.recursive_stability:
            result = orchestrator.run_until_stable(
                request.query, max_iterations=request.max_iterations
            )
        else:
            result = orchestrator.execute(request.query)

        return RegimeResponse(**result)
    except BlueprintError as exc:
        # The plan could not be executed; the message names the function or argument at fault.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Anything else is the platform's fault: log it, tell the caller nothing about it.
        logger.exception("query failed")
        raise HTTPException(status_code=500, detail="Internal error") from exc


if __name__ == "__main__":
    import uvicorn

    # Loopback by default: the API has no authentication. The Docker image sets HOST=0.0.0.0.
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
