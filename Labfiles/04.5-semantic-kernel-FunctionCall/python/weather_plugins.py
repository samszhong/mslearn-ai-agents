from semantic_kernel.functions.kernel_function_decorator import kernel_function

class WeatherPlugin:
    """Plugin for current weather information."""
    @kernel_function(description="Get current weather for a location and optional country.")
    def get_weather(self, location: str, country: str = None) -> str:
        import requests, json
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
