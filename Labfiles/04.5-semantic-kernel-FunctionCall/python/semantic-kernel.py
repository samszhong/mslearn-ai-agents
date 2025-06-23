import os
import asyncio
from pathlib import Path

# Add references
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from semantic_kernel.functions import kernel_function
from typing import Annotated

from weather_plugins import WeatherPlugin, WeatherForecastPlugin

async def main():
    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    # Ask for a location
    location_data = input("\nPlease enter the weather location (e.g., city or city,country) and optionall you can let the agent know if you want current weather or forecast\n\n")
    # Run the async agent code
    await process_weather_data(location_data)

#async def process_weather_data(prompt, location_data):
async def process_weather_data(location_data):    

    # Get configuration settings
    load_dotenv()
    project_endpoint= os.getenv("AZURE_AI_AGENT_PROJECT_CONNECTION_STRING")
    model_deployment = os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME")
    ai_agent_settings = AzureAIAgentSettings()


    # Connect to the Azure AI Foundry project
    async with (
        DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True) as creds,
        AzureAIAgent.create_client(
            endpoint=project_endpoint,
            credential=creds
        ) as project_client,
    ):

        
        # Define an Azure AI agent for weather info
        weather_agent_def = await project_client.agents.create_agent(
            model= ai_agent_settings.model_deployment_name,
            name="weather_agent",
            instructions="""You are an AI agent that retrieves current weather or a 
            5-day weather forecast for a given location using a function call. 
            If the user asks for a forecast, use the WeatherForecastPlugin. 
            If the user asks for current weather, use the WeatherPlugin.
            If the user give a location only, get both the current weather and 
            the 5-day forecast for that location."""
        )


        # Create a semantic kernel agent with weather plugins
        weather_agent = AzureAIAgent(
            client=project_client,
            definition=weather_agent_def,
            plugins=[WeatherPlugin(), WeatherForecastPlugin()]
        )


        # Use the agent to process the weather data
        thread: AzureAIAgentThread = AzureAIAgentThread(client=project_client)
        try:
            # Add the input prompt to a list of messages to be submitted
            prompt_messages = [f"{location_data}"]
            # Invoke the agent for the specified thread with the messages
            response = await weather_agent.get_response(thread_id=thread.id, messages=prompt_messages)
            # Display the response
            print(f"\n# {response.name}:\n{response}")
        except Exception as e:
            # Something went wrong
            print (e)
        finally:
            # Cleanup: Delete the thread and agent
            await thread.delete() if thread else None
            await project_client.agents.delete_agent(weather_agent.id)


if __name__ == "__main__":
    asyncio.run(main())
