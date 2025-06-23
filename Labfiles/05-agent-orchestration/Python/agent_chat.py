
# Load environment variables from .env file
from dotenv import load_dotenv
import asyncio
import os
import textwrap
from datetime import datetime
from pathlib import Path
import shutil

# Azure and Semantic Kernel imports
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AgentGroupChat
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.agents.strategies import TerminationStrategy, SequentialSelectionStrategy
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.functions.kernel_function_decorator import kernel_function


# Agent names and instructions
INCIDENT_MANAGER = "INCIDENT_MANAGER"
# Instructions for the INCIDENT_MANAGER agent
INCIDENT_MANAGER_INSTRUCTIONS = """
Analyze the given log file or the response from the devops assistant.
Recommend which one of the following actions should be taken:

Restart service {service_name}
Rollback transaction
Redeploy resource {resource_name}
Increase quota

If there are no issues or if the issue has already been resolved, respond with "INCIDENT_MANAGER > No action needed."
If none of the options resolve the issue, respond with "Escalate issue."

RULES:
- Do not perform any corrective actions yourself.
- Read the log file on every turn.
- Prepend your response with this text: "INCIDENT_MANAGER > {logfilepath} | "
- Only respond with the corrective action instructions.
"""

DEVOPS_ASSISTANT = "DEVOPS_ASSISTANT"
# Instructions for the DEVOPS_ASSISTANT agent
DEVOPS_ASSISTANT_INSTRUCTIONS = """
Read the instructions from the INCIDENT_MANAGER and apply the appropriate resolution function. 
Return the response as "{function_response}"
If the instructions indicate there are no issues or actions needed, 
take no action and respond with "No action needed."

RULES:
- Use the instructions provided.
- Do not read any log files yourself.
- Prepend your response with this text: "DEVOPS_ASSISTANT > "
"""


# Main async function to run the agent orchestration
async def main():
    # Load environment variables from .env file
    load_dotenv()

    # Clear the console for better readability
    os.system('cls' if os.name=='nt' else 'clear')

    # Copy sample log files to a working directory
    print("Getting log files...\n")
    script_dir = Path(__file__).parent  # Get the directory of the script
    src_path = script_dir / "sample_logs"
    file_path = script_dir / "logs"
    shutil.copytree(src_path, file_path, dirs_exist_ok=True)

    # Get the Azure AI endpoint from environment variable
    # NOTE: Update the environment variable name if needed
    azure_ai_endpoint = os.environ.get("AZURE_AI_AGENT_PROJECT_CONNECTION_STRING")
    if not azure_ai_endpoint:
        raise RuntimeError("Please set the AZURE_AI_ENDPOINT environment variable.")


    # Create Azure AI Agent settings with the endpoint
    ai_agent_settings = AzureAIAgentSettings(endpoint=azure_ai_endpoint)

    # Create Azure credentials and client for the Azure AI Agent
    async with (
        DefaultAzureCredential(exclude_environment_credential=True, 
            exclude_managed_identity_credential=True) as creds,
        AzureAIAgent.create_client(endpoint=azure_ai_endpoint, credential=creds) as client,
    ):
        # Create the INCIDENT_MANAGER agent definition on the Azure AI agent service
        incident_agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=INCIDENT_MANAGER,
            instructions=INCIDENT_MANAGER_INSTRUCTIONS
        )

        # Create a Semantic Kernel agent for the INCIDENT_MANAGER
        agent_incident = AzureAIAgent(
            client=client,
            definition=incident_agent_definition,
            plugins=[LogFilePlugin()]
        )

        # Create the DEVOPS_ASSISTANT agent definition on the Azure AI agent service
        devops_agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=DEVOPS_ASSISTANT,
            instructions=DEVOPS_ASSISTANT_INSTRUCTIONS,
        )

        # Create a Semantic Kernel agent for the DEVOPS_ASSISTANT
        agent_devops = AzureAIAgent(
            client=client,
            definition=devops_agent_definition,
            plugins=[DevopsPlugin()]
        )

        # Add both agents to a group chat with custom termination and selection strategies
        chat = AgentGroupChat(
            agents=[agent_incident, agent_devops],
            termination_strategy=ApprovalTerminationStrategy(
                agents=[agent_incident], 
                maximum_iterations=10, 
                automatic_reset=True
            ),
            selection_strategy=SelectionStrategy(agents=[agent_incident,agent_devops]),      
        )

        # Process each log file in the working directory
        for filename in os.listdir(file_path):
            logfile_msg = ChatMessageContent(role=AuthorRole.USER, content=f"USER > {file_path}/{filename}")
            await asyncio.sleep(30) # Wait to reduce TPM (tokens per minute)
            print(f"\nReady to process log file: {filename}\n")

            # Add the current log file as a chat message
            await chat.add_chat_message(logfile_msg)
            print()

            try:
                print()
                # Invoke a response from the agents for the current log file
                async for response in chat.invoke():
                    if response is None or not response.name:
                        continue
                    print(f"{response.content}")
            except Exception as e:
                print(f"Error during chat invocation: {e}")
                # If TPM rate exceeded, wait 60 secs and retry
                if "Rate limit is exceeded" in str(e):
                    print ("Waiting...")
                    await asyncio.sleep(60)
                    continue
                else:
                    break




# Custom selection strategy: determines which agent should take the next turn
class SelectionStrategy(SequentialSelectionStrategy):
    """A strategy for determining which agent should take the next turn in the chat."""

    async def select_agent(self, agents, history):
        """Check which agent should take the next turn in the chat."""
        # The Incident Manager should go after the User or the DevOps Assistant
        if (history[-1].name == DEVOPS_ASSISTANT or history[-1].role == AuthorRole.USER):
            agent_name = INCIDENT_MANAGER
            return next((agent for agent in agents if agent.name == agent_name), None)
        # Otherwise it is the DevOps Assistant's turn
        return next((agent for agent in agents if agent.name == DEVOPS_ASSISTANT), None)




# Custom termination strategy: ends the chat if no action is needed
class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""

    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        return "no action needed" in history[-1].content.lower()




# Plugin class for DevOps functions (actions the DevOps agent can perform)
class DevopsPlugin:
    """A plugin that performs developer operation tasks."""

    def append_to_log_file(self, filepath: str, content: str) -> None:
        # Appends content to the specified log file
        with open(filepath, 'a', encoding='utf-8') as file:
            file.write('\n' + textwrap.dedent(content).strip())

    @kernel_function(description="A function that restarts the named service")
    def restart_service(self, service_name: str = "", logfile: str = "") -> str:
        # Simulate restarting a service and log the action
        log_entries = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: Multiple failures detected in {service_name}. Restarting service.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO  {service_name}: Restart initiated.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO  {service_name}: Service restarted successfully.",
        ]
        log_message = "\n".join(log_entries)
        self.append_to_log_file(logfile, log_message)
        return f"Service {service_name} restarted successfully."

    @kernel_function(description="A function that rollsback the transaction")
    def rollback_transaction(self, logfile: str = "") -> str:
        # Simulate rolling back a transaction and log the action
        log_entries = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: Transaction failure detected. Rolling back transaction batch.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   TransactionProcessor: Rolling back transaction batch.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   Transaction rollback completed successfully.",
        ]
        log_message = "\n".join(log_entries)
        self.append_to_log_file(logfile, log_message)
        return "Transaction rolled back successfully."

    @kernel_function(description="A function that redeploys the named resource")
    def redeploy_resource(self, resource_name: str = "", logfile: str = "") -> str:
        # Simulate redeploying a resource and log the action
        log_entries = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: Resource deployment failure detected in '{resource_name}'. Redeploying resource.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   DeploymentManager: Redeployment request submitted.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   DeploymentManager: Service successfully redeployed, resource '{resource_name}' created successfully.",
        ]
        log_message = "\n".join(log_entries)
        self.append_to_log_file(logfile, log_message)
        return f"Resource '{resource_name}' redeployed successfully."

    @kernel_function(description="A function that increases the quota")
    def increase_quota(self, logfile: str = "") -> str:
        # Simulate increasing quota and log the action
        log_entries = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: High request volume detected. Increasing quota.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   APIManager: Quota increase request submitted.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] INFO   APIManager: Quota successfully increased to 150% of previous limit.",
        ]
        log_message = "\n".join(log_entries)
        self.append_to_log_file(logfile, log_message)
        return "Successfully increased quota."

    @kernel_function(description="A function that escalates the issue")
    def escalate_issue(self, logfile: str = "") -> str:
        # Simulate escalating an issue and log the action
        log_entries = [
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: Cannot resolve issue.",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ALERT  DevopsAssistant: Requesting escalation.",
        ]
        log_message = "\n".join(log_entries)
        self.append_to_log_file(logfile, log_message)
        return "Submitted escalation request."



# Plugin class for log file access (used by the INCIDENT_MANAGER agent)
class LogFilePlugin:
    """A plugin that reads and writes log files."""

    @kernel_function(description="Accesses the given file path string and returns the file contents as a string")
    def read_log_file(self, filepath: str = "") -> str:
        # Reads and returns the contents of the specified log file
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()



# Entry point: start the async main function
if __name__ == "__main__":
    asyncio.run(main())