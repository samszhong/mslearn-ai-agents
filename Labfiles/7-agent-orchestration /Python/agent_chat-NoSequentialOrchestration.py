
# Load environment variables from .env file
from dotenv import load_dotenv
import asyncio
import os

# Azure and Semantic Kernel imports
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import SequentialOrchestration
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.functions.kernel_function_decorator import kernel_function


# Agent names and instructions
WEATHER_MANAGER = "WEATHER_MANAGER"
# Instructions for the INCIDENT_MANAGER agent
WEATHER_MANAGER_INSTRUCTIONS = """

For a given location (city or city,country), get the 5-day weather forecast. 

"""

CAMPING_ASSISTANT = "CAMPING_ASSISTANT"
# Instructions for the CAMPING_ASSISTANT agent
CAMPING_ASSISTANT_INSTRUCTIONS = """
Read the weather forecast from the weather_agent and create a shopping list based on the weather forecast. 

"""


# Main async function to run the agent orchestration
async def main():
    # Load environment variables from .env file
    load_dotenv()

    # Clear the console for better readability
    os.system('cls' if os.name=='nt' else 'clear')

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
        weather_agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=WEATHER_MANAGER,
            instructions=WEATHER_MANAGER_INSTRUCTIONS
        )

        # Create a Semantic Kernel agent for the WEATHER_MANAGER
        agent_weather = AzureAIAgent(
            client=client,
            definition=weather_agent_definition,
            plugins=[WeatherForecastPlugin()]  # Pass an instance, not the class
        )

        # Create the DEVOPS_ASSISTANT agent definition on the Azure AI agent service
        camping_agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=CAMPING_ASSISTANT,
            instructions=CAMPING_ASSISTANT_INSTRUCTIONS,
        )

        # Create a Semantic Kernel agent for the CAMPING_ASSISTANT
        agent_camping = AzureAIAgent(
            client=client,
            definition=camping_agent_definition
        )



        # Prompt user for location
        user_location = input("Enter a location (city or city,country) for your camping trip: ")
        USER_INPUTS = [user_location]

        # Step 1: Get weather forecast from agent_weather
        weather_result = await agent_weather.get_response(messages=USER_INPUTS)
        print(f"Weather forecast for camping: {weather_result}")

        # Step 2: Pass weather forecast to agent_camping for recommendations
        camping_prompt = f"Based on this weather forecast, what items should I bring for a camping trip?\n\n{weather_result}"
        camping_result = await agent_camping.get_response(messages=[camping_prompt])
        print(f"***** Camping Recommendations *****\n{camping_result}")

     


# WeatherForecastPlugin
class WeatherForecastPlugin:
    """Plugin for 5-day weather forecast."""
    @kernel_function(description="Get 5-day weather forecast for a location and optional country.")
    def get_weather_forecast(self, location: str, country: str = None) -> str:
        import requests, json, statistics
        from collections import defaultdict
        api_key = "3a9a78b47e4fa3b057d71dbf99b4f392"
        if country:
            query = f"{location},{country}"
        else:
            query = location
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={query}&units=metric&appid={api_key}"
        response = requests.get(url)
        if response.status_code != 200:
            return json.dumps({"message": f"Could not retrieve weather forecast for {query}."})
        forecast_data = response.json()
        daily_data = defaultdict(list)
        for entry in forecast_data.get('list', []):
            date = entry['dt_txt'].split(' ')[0]
            temp = entry['main']['temp']
            weather = entry['weather'][0]['description']
            daily_data[date].append((temp, weather))
        daily_summary = {}
        for date, values in daily_data.items():
            temps = [v[0] for v in values]
            weather_descriptions = [v[1] for v in values]
            try:
                most_common_weather = statistics.mode(weather_descriptions)
            except statistics.StatisticsError:
                most_common_weather = weather_descriptions[0] if weather_descriptions else "N/A"
            daily_summary[date] = {
                'min_temp': min(temps),
                'max_temp': max(temps),
                'weather': most_common_weather
            }
        summary_lines = []
        for date, summary in daily_summary.items():
            summary_lines.append(f"{date}: {summary['min_temp']}°C - {summary['max_temp']}°C, {summary['weather']}")
        return json.dumps({"forecast": summary_lines})



# Entry point: start the async main function
if __name__ == "__main__":
    asyncio.run(main())