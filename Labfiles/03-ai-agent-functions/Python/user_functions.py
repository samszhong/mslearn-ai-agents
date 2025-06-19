import json
from pathlib import Path
import uuid
from typing import Any, Callable, Set
import requests



# Create a function to retrieve weather information for a given location and optional country
def get_weather(location: str, country: str = None) -> str:
    api_key = "3a9a78b47e4fa3b057d71dbf99b4f392"
    if country:
        query = f"{location},{country}"
    else:
        query = location
    url = f"https://api.openweathermap.org/data/2.5/weather?q={query}&APPID={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        weather = data.get('weather', [{}])[0].get('description', 'No description')
        temp = data.get('main', {}).get('temp', 'N/A')
        city = data.get('name', location)
        country_resp = data.get('sys', {}).get('country', '')
        message = f"Weather in {city}, {country_resp}: {weather}, Temperature: {temp}°C"
    else:
        message = f"Could not retrieve weather information for {query}."
    return json.dumps({"message": message})


# Create a function to retrieve a 5-day weather forecast for a given location and optional country
from collections import defaultdict
from datetime import datetime
import statistics

def get_weather_forecast(location: str, country: str = None) -> str:
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
    # Format the summary for output
    summary_lines = []
    for date, summary in daily_summary.items():
        summary_lines.append(f"{date}: {summary['min_temp']}°C - {summary['max_temp']}°C, {summary['weather']}")
    return json.dumps({"forecast": summary_lines})

# Define a set of callable functions
user_functions: Set[Callable[..., Any]] = {
    get_weather,
    get_weather_forecast
}


