import requests
import logging

# Strava API credentials
CLIENT_ID = 'your_id'
CLIENT_SECRET = 'your_secret'
REFRESH_TOKEN = 'your_token'
ACCESS_TOKEN = 'your_token'

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

def get_recent_activities():
    response = requests.get(
        'https://www.strava.com/api/v3/athlete/activities',
        headers={'Authorization': f'Bearer {ACCESS_TOKEN}'},
        params={'per_page': 5, 'page': 1}
    )
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        refresh_access_token()
        return get_recent_activities()
    else:
        logging.error(f"Failed to get activities: {response.status_code}")
        return []

def get_activity_details(activity_id):
    url = f'https://www.strava.com/api/v3/activities/{activity_id}'
    response = requests.get(
        url,
        headers={'Authorization': f'Bearer {ACCESS_TOKEN}'}
    )
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Failed to get activity details: {response.status_code}")
        return None
