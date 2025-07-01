# Load environment variables from .env file
from dotenv import load_dotenv
import asyncio
import os

import time
import json

from azure.ai.agents.models import MessageTextContent, ListSortOrder
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

load_dotenv()

# Clear the console for better readability
os.system('cls' if os.name=='nt' else 'clear')

# Get the Azure AI endpoint from environment variable
# NOTE: Update the environment variable name if needed
PROJECT_ENDPOINT = os.environ.get("AZURE_AI_AGENT_PROJECT_CONNECTION_STRING")
if not PROJECT_ENDPOINT:
    raise RuntimeError("Please set the PROJECT_ENDPOINT environment variable.")

MODEL_DEPLOYMENT_NAME = os.environ.get("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME")
if not MODEL_DEPLOYMENT_NAME:
    raise RuntimeError("Please set the MODEL_DEPLOYMENT_NAME environment variable.")




project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential()
)

with project_client:
    agent = project_client.agents.create_agent(
        model=MODEL_DEPLOYMENT_NAME, 
        name="my-mcp-agent", 
        instructions="You are a helpful assistant. Use the tools provided to answer the user's questions. Be sure to cite your sources.",
        tools= [
            {
                "type": "mcp",
        "server_label": "github",
                "server_url": "https://gitmcp.io/Azure/azure-rest-api-specs",
                "require_approval": "never"
            }
        ],
        tool_resources=None
    )
    print(f"Created agent, agent ID: {agent.id}")

    thread = project_client.agents.threads.create()
    print(f"Created thread, thread ID: {thread.id}")

    message = project_client.agents.messages.create(
        thread_id=thread.id, role="user", content="<a question for your MCP server>",
    )
    print(f"Created message, message ID: {message.id}")

    run = project_client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)


    
    # Poll the run as long as run status is queued or in progress
    while run.status in ["queued", "in_progress", "requires_action"]:
        # Wait for a second
        time.sleep(1)
        run = project_client.agents.runs.get(thread_id=thread.id, run_id=run.id)
        print(f"Run status: {run.status}")

    if run.status == "failed":
        print(f"Run error: {run.last_error}")

    run_steps = project_client.agents.run_steps.list(thread_id=thread.id, run_id=run.id)
    for step in run_steps:
        print(f"Run step: {step.id}, status: {step.status}, type: {step.type}")
        if step.type == "tool_calls":
            print(f"Tool call details:")
            for tool_call in step.step_details.tool_calls:
                print(json.dumps(tool_call.as_dict(), indent=2))

    messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    for data_point in messages:
        last_message_content = data_point.content[-1]
        if isinstance(last_message_content, MessageTextContent):
            print(f"{data_point.role}: {last_message_content.text.value}")


    project_client.agents.delete_agent(agent.id)
    print(f"Deleted agent, agent ID: {agent.id}")