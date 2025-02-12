from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv
from agent_workflow import get_agent

# Configuration
@dataclass
class Settings:
    API_VERSION: str = "v1"
    API_TITLE: str = "Medical Appointment Agent API"
    API_DESCRIPTION: str = "API for medical appointment scheduling AI Agents"
    DEFAULT_QUERY: str = """Find all orthopedic specialist (knee doctor) who: 
        1. Accepts uninsured patients 
        2. Has availability for appointments on Mondays between 8:00 - 12:00 CET 
        3. Can schedule a 30 min appointment for February 2025."""
    PROMPT_EXTENSION: str = """
        The final answer should be complete information a patient can use to make an informed decision regarding points 1, 2, and 3. 
        If no slots are available or no doctors were found, please inform the patient. 
        Answer in a complete sentence or paragraph in human readable form.
        """

# Models
class Query(BaseModel):
    user_input: str = Field(
        default=Settings.DEFAULT_QUERY,
        description="User query for medical appointment scheduling"
    )

class HealthResponse(BaseModel):
    status: str
    version: str

class ErrorResponse(BaseModel):
    detail: str

# Application setup
def create_app() -> FastAPI:
    load_dotenv()
    
    app = FastAPI(
        title=Settings.API_TITLE,
        description=Settings.API_DESCRIPTION,
        version=Settings.API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    setup_cors(app)
    setup_routes(app)
    
    return app

def setup_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Dependencies
@lru_cache()
def get_settings() -> Settings:
    return Settings()

@lru_cache()
def get_agent_singleton():
    """Cached agent instance to prevent multiple initializations"""
    return get_agent()

# Route handlers
async def process_query(
    query: Query,
    settings: Settings = Depends(get_settings),
    agent = Depends(get_agent_singleton)
) -> Dict[str, Any]:
    try:
        full_prompt = f"{query.user_input}{settings.PROMPT_EXTENSION}"
        output = agent.run(full_prompt)
        return {"answer": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="healthy", version=settings.API_VERSION)

async def get_root() -> Dict[str, Any]:
    return {
        "message": "Welcome to the Medical Appointment Agent API",
        "version": Settings.API_VERSION,
        "documentation": "/docs",
        "health_check": "/health",
        "usage": "Send a POST request to /query with a JSON body containing a 'user_input' field."
    }

# Route setup
def setup_routes(app: FastAPI) -> None:
    app.post("/query", response_model=Dict[str, Any], responses={500: {"model": ErrorResponse}})(process_query)
    app.get("/health", response_model=HealthResponse)(get_health)
    app.get("/")(get_root)

# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)