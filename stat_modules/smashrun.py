import requests

# Smashrun access token
ACCESS_TOKEN = 'your_access_token'

def get_notables():
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    response = requests.get('https://api.smashrun.com/v1/my/activities', headers=headers)

    if response.status_code == 200:
        activities = response.json()
        if activities:
            latest_activity_id = activities[0]['activityId']
            notables_response = requests.get(f'https://api.smashrun.com/v1/my/activities/{latest_activity_id}/notables', headers=headers)
            
            if notables_response.status_code == 200:
                notables = notables_response.json()
                descriptions = [notable['description'] for notable in notables]
                return descriptions
            else:
                print(f"Failed to get notables: {notables_response.status_code}")
                return []
        else:
            print("No activities found")
            return []
    else:
        print(f"Failed to get activities: {response.status_code}")
        return []

if __name__ == "__main__":
    notables = get_notables()
    if notables:
        for notable in notables:
            print(notable)
    else:
        print("No notables found for the latest activity.")
