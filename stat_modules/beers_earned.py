import requests
import logging

# Strava API credentials
CLIENT_ID = 'your_id'
CLIENT_SECRET = 'your_secret'
REFRESH_TOKEN = 'your_token'
ACCESS_TOKEN = 'your_token'

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

# Function to get recent activities
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
        return []

# Function to get detailed activity data
def get_activity_details(activity_id):
    url = f'https://www.strava.com/api/v3/activities/{activity_id}'
    response = requests.get(
        url,
        headers={'Authorization': f'Bearer {ACCESS_TOKEN}'}
    )
    if response.status_code == 200:
        return response.json()

# Function to calculate beers earned from calories burned
def calculate_beers(activity):
    activity_calories = activity.get('calories', 0)
    if activity_calories:
        beers_earned = activity_calories / 150  # 150 calories per beer
    else:
        beers_earned = 0
    return beers_earned

if __name__ == "__main__":
    recent_activities = get_recent_activities()
    
    if recent_activities:
        latest_activity = recent_activities[0]
        detailed_activity = get_activity_details(latest_activity['id'])
        
        if detailed_activity:
            beers = calculate_beers(detailed_activity)
            print(f"Beers earned for the latest running activity: {beers:.1f}")
    else:
        print("No recent activities found")
