"""Chat web app for the private Foundry RAG agent.

Runs in Azure Container Apps (internal environment). Authenticates to the
Foundry project with the container app's managed identity - no keys.
"""
import logging
import os

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("rag-agent-webapp")

PROJECT_ENDPOINT = os.environ.get("PROJECT_ENDPOINT", "")
AGENT_ID = os.environ.get("AGENT_ID", "")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="RAG Agent Web App")
_client: AgentsClient | None = None


def get_client() -> AgentsClient:
    global _client
    if _client is None:
        if not PROJECT_ENDPOINT or not AGENT_ID:
            raise HTTPException(500, "PROJECT_ENDPOINT and AGENT_ID must be set")
        _client = AgentsClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    return _client


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    citations: list[str] = []


@app.get("/health")
def health() -> dict:
    # Kept dependency-free so App Gateway / Container Apps probes stay fast.
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(400, "message is empty")

    client = get_client()
    thread_id = req.thread_id or client.threads.create().id

    client.messages.create(thread_id=thread_id, role="user", content=req.message)
    run = client.runs.create_and_process(thread_id=thread_id, agent_id=AGENT_ID)
    if run.status == "failed":
        log.error("Agent run failed: %s", run.last_error)
        raise HTTPException(502, f"Agent run failed: {run.last_error}")

    answer, citations = "", []
    for msg in client.messages.list(thread_id=thread_id, order=ListSortOrder.DESCENDING):
        if msg.role == "assistant" and msg.text_messages:
            answer = msg.text_messages[-1].text.value
            for ann in getattr(msg, "url_citation_annotations", None) or []:
                cite = ann.url_citation
                citations.append(cite.title or cite.url)
            break

    return ChatResponse(answer=answer, thread_id=thread_id, citations=citations)
