# RAG Agent Web App

Chat front end for the private Microsoft Foundry agent (RAG over Azure AI Search).
Hosted on Azure Container Apps (internal environment), built and deployed by Azure Pipelines.

## Structure

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app: `GET /` chat page, `POST /chat` calls the Foundry agent, `GET /health` probe |
| `app/static/index.html` | Chat page |
| `scripts/clone_agent.py` | Clone an agent (same or another project, optional model / search override, export to JSON) |
| `Dockerfile` | Container image (port 8000, non-root user) |
| `azure-pipelines.yml` | `az acr build` -> `az containerapp update` |

## Configuration (environment variables)

| Name | Example |
|---|---|
| `PROJECT_ENDPOINT` | `https://aif-ragagent-prv-jpe.services.ai.azure.com/api/projects/proj-ragagent-prv` |
| `AGENT_ID` | `asst_xxxxxxxx` |

Authentication uses `DefaultAzureCredential`: the Container App's system-assigned managed
identity in Azure (needs the **Foundry User / Azure AI User** role on the Foundry resource),
or your `az login` session when run on the jumpbox. No keys are used.

## Run locally (jumpbox only - Foundry is private)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
az login
$env:PROJECT_ENDPOINT = "<project endpoint>"
$env:AGENT_ID = "<agent id>"
uvicorn app.main:app --port 8000
```
Open http://localhost:8000

## Clone an agent

```powershell
python scripts/clone_agent.py --source-agent-id asst_xxx --name agent-ragagent-prv-clone
python scripts/clone_agent.py --source-agent-id asst_xxx --name agent-upgrade-test --model gpt-4.1
python scripts/clone_agent.py --source-agent-id asst_xxx --export agent.json
```

## Deploy

Push to `main` in Azure Repos. The pipeline builds the image in ACR, sets the Container App's
target port to 8000 and the `PROJECT_ENDPOINT` / `AGENT_ID` settings, and rolls out a new revision.
Pipeline variables `projectEndpoint` and `agentId` must be set in Azure DevOps.
