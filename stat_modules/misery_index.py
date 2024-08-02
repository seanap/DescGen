import requests
import logging
from datetime import datetime, timezone

# Strava API credentials
CLIENT_ID = 'your_id'
CLIENT_SECRET = 'your_secret'
REFRESH_TOKEN = 'your_token'
ACCESS_TOKEN = 'your_token'

# WeatherAPI credentials
WEATHER_API_KEY = 'your_weatherapi_key'

# Function to refresh Strava access token
def refresh_access_token():
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'refresh_token': REFRESH_TOKEN,
            'grant_type': 'refresh_token'
        }
    )
    response_data = response.json()
    if response.status_code == 200:
        global ACCESS_TOKEN
        ACCESS_TOKEN = response_data['access_token']
        logging.info("Access token refreshed")
    else:
        logging.error(f"Error refreshing access token: {response_data}")

# Function to get the most recent Strava activity
def get_recent_strava_activity():
    url = 'https://www.strava.com/api/v3/athlete/activities'
    headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
    params = {'per_page': 1, 'page': 1}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 401:
        logging.error("Access token expired, refreshing...")
        refresh_access_token()
        return get_recent_strava_activity()
    
    if response.status_code == 200:
        activity = response.json()[0]
        return activity
    else:
        logging.error(f"Failed to get Strava activity: {response.status_code}")
        return None

# Function to get weather data based on time, date, and location
def get_weather_data(lat, lon, timestamp):
    date_time = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
    
    url = f"http://api.weatherapi.com/v1/history.json?key={WEATHER_API_KEY}&q={lat},{lon}&dt={date_time}"
    response = requests.get(url)
    
    if response.status_code == 200:
        weather_data = response.json()
        hour_data = weather_data['forecast']['forecastday'][0]['hour'][0]  # Assuming the first hour
        temp_f = hour_data['temp_f']
        dew_point_f = hour_data['dewpoint_f']
        humidity = hour_data['humidity']
        wind_speed_mph = hour_data['wind_mph']
        return temp_f, dew_point_f, humidity, wind_speed_mph
    else:
        logging.error(f"Failed to get weather data: {response.status_code}")
        return None, None, None, None

# Function to calculate Misery Index
def calculate_misery_index(temp_f, dew_point_f, humidity, wind_speed_mph):
    misery_index = (temp_f + ((dew_point_f * 2) + humidity) / 3) - (wind_speed_mph * (1 - (humidity / 100)))
    return round(misery_index, 1)

# Function to determine Misery Index description
def get_misery_index_description(misery_index):
    if 130 <= misery_index < 140:
        return "😅 Mildly Uncomfortable"
    elif 140 <= misery_index < 145:
        return "😓 Moderately Uncomfortable"
    elif 145 <= misery_index < 150:
        return "😰 Very Uncomfortable"
    elif 150 <= misery_index < 155:
        return "🥵 Oppressive"
    elif 155 <= misery_index < 160:
        return "😡 Miserable - Why??"
    elif misery_index >= 160:
        return "☠️⚠️High risk: Heat-Exhaustion"
    else:
        return "😀 Pleasant running conditions"

# Function to get Misery Index and its description
def get_misery_index():
    activity = get_recent_strava_activity()
    if not activity:
        return None, None
    
    lat, lon = activity['start_latlng']
    timestamp = int(datetime.strptime(activity['start_date_local'], '%Y-%m-%dT%H:%M:%SZ').timestamp())
    
    temp_f, dew_point_f, humidity, wind_speed_mph = get_weather_data(lat, lon, timestamp)
    
    if temp_f and dew_point_f and humidity and wind_speed_mph:
        misery_index = calculate_misery_index(temp_f, dew_point_f, humidity, wind_speed_mph)
        description = get_misery_index_description(misery_index)
        return misery_index, description
    else:
        return None, None

if __name__ == "__main__":
    misery_index, description = get_misery_index()
    if misery_index:
        print(f"Misery Index: {misery_index}")
        print(f"Description: {description}")
    else:
        print("No Misery Index calculated due to missing data.")
