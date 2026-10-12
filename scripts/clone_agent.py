"""Clone a Foundry agent (classic Agents API, asst_... IDs).

Copies model, instructions, tools, tool resources (e.g. the Azure AI Search
knowledge source) and model settings into a new agent - in the same project or
in another project.

Examples (run from a machine that can reach the private Foundry endpoint,
e.g. the jumpbox, after `az login`):

  # Clone within the same project
  python scripts/clone_agent.py --source-agent-id asst_xxx --name agent-ragagent-prv-clone

  # Clone and switch the model (model-upgrade test)
  python scripts/clone_agent.py --source-agent-id asst_xxx --name agent-upgrade-test --model gpt-4.1

  # Clone into another project (search connection/index differ there)
  python scripts/clone_agent.py --source-agent-id asst_xxx --name agent-copy \
      --target-endpoint https://<other>.services.ai.azure.com/api/projects/<proj> \
      --search-connection-id <connection resource id in target project> --index-name <index>

  # Export the definition to a file (backup / review / source control)
  python scripts/clone_agent.py --source-agent-id asst_xxx --export agent.json
"""
import argparse
import json
import os
import sys

from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential

COPY_FIELDS = ["model", "instructions", "description", "tools", "tool_resources",
               "temperature", "top_p", "response_format", "metadata"]


def main() -> int:
    p = argparse.ArgumentParser(description="Clone a Foundry agent")
    p.add_argument("--source-endpoint", default=os.environ.get("PROJECT_ENDPOINT"),
                   help="Project endpoint of the source agent (default: $PROJECT_ENDPOINT)")
    p.add_argument("--source-agent-id", required=True)
    p.add_argument("--name", help="Name for the new agent")
    p.add_argument("--target-endpoint", help="Project endpoint for the clone (default: same project)")
    p.add_argument("--model", help="Override the model deployment name")
    p.add_argument("--search-connection-id", help="Override Azure AI Search connection id")
    p.add_argument("--index-name", help="Override Azure AI Search index name")
    p.add_argument("--export", help="Write the source definition to this JSON file and exit")
    args = p.parse_args()

    if not args.source_endpoint:
        p.error("--source-endpoint or PROJECT_ENDPOINT is required")

    cred = DefaultAzureCredential()
    source = AgentsClient(endpoint=args.source_endpoint, credential=cred)
    agent = source.get_agent(args.source_agent_id).as_dict()
    definition = {k: agent[k] for k in COPY_FIELDS if agent.get(k) is not None}

    if args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump({"name": agent.get("name"), **definition}, f, indent=2)
        print(f"Exported {args.source_agent_id} to {args.export}")
        return 0

    if args.model:
        definition["model"] = args.model

    if args.search_connection_id or args.index_name:
        indexes = (definition.get("tool_resources") or {}).get("azure_ai_search", {}).get("indexes", [])
        if not indexes:
            sys.exit("Source agent has no Azure AI Search tool resource to override")
        for idx in indexes:
            if args.search_connection_id:
                idx["index_connection_id"] = args.search_connection_id
            if args.index_name:
                idx["index_name"] = args.index_name

    target = AgentsClient(endpoint=args.target_endpoint, credential=cred) if args.target_endpoint else source
    clone = target.create_agent(name=args.name or f"{agent.get('name')}-clone", **definition)

    print(f"Source : {args.source_agent_id} ({agent.get('name')}, model {agent.get('model')})")
    print(f"Clone  : {clone.id} ({clone.name}, model {clone.model})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
