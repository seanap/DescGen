import requests
from datetime import datetime, timedelta

# Strava API credentials
CLIENT_ID = 'your_id'
CLIENT_SECRET = 'your_secret'
REFRESH_TOKEN = 'your_token'
ACCESS_TOKEN = 'your_token'

# Function to refresh the Strava access token
def refresh_access_token():
    global ACCESS_TOKEN
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
        ACCESS_TOKEN = response_data['access_token']
        print("Access token refreshed successfully")
    else:
        print(f"Error refreshing access token: {response_data}")

# Function to fetch activities from Strava
def get_activities(access_token, after_date=None):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    params = {
        "per_page": 100,  # fetch 100 activities at a time
        "page": 1
    }

    if after_date:
        after_timestamp = int(after_date.timestamp())
        params["after"] = after_timestamp

    activities = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed to get data: {response.status_code}")
            return None
        
        data = response.json()
        if not data:
            break
        activities.extend(data)
        params["page"] += 1

    return activities

# Function to calculate the current streak
def get_streak(access_token):
    # Define the start date to fetch activities from (e.g., start of 2024)
    start_date = datetime(2024, 1, 1)
    
    activities = get_activities(access_token, after_date=start_date)
    if not activities:
        return None

    streak = 0
    current_date = datetime.now().date()

    days_with_activities = set()

    for activity in activities:
        activity_date = datetime.strptime(activity['start_date_local'], "%Y-%m-%dT%H:%M:%S%z").date()
        days_with_activities.add(activity_date)

    # Start the streak calculation from the most recent activity date
    last_activity_date = max(days_with_activities)
    
    # Check for consecutive days starting from the most recent activity date
    while last_activity_date in days_with_activities:
        streak += 1
        last_activity_date -= timedelta(days=1)

    return streak

if __name__ == "__main__":
    refresh_access_token()  # Refresh the access token first
    
    current_streak = get_streak(ACCESS_TOKEN)
    print(f"Current streak: {current_streak} days")
