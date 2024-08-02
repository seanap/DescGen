from garminconnect import Garmin
import datetime

# Garmin Connect credentials
EMAIL = 'garmin_email'
PASSWORD = 'garmin_pass'

def get_vo2max():
    client = Garmin(EMAIL, PASSWORD)
    client.login()

    # Fetch recent activities (e.g., last 5 to cover recent days)
    activities = client.get_activities(0, 5)

    for activity in activities:
        try:
            # Attempt to fetch VO2 max data for the date of this activity
            activity_date = activity['startTimeLocal'].split(' ')[0]
            vo2max_data = client.get_max_metrics(activity_date)
            if vo2max_data and 'generic' in vo2max_data[0] and 'vo2MaxValue' in vo2max_data[0]['generic']:
                return vo2max_data[0]['generic']['vo2MaxValue']
        except Exception as e:
            print(f"Error fetching VO2Max data for {activity_date}: {e}")
            continue

    return None

if __name__ == "__main__":
    vo2max_value = get_vo2max()
    if vo2max_value:
        print(f"VO2Max: {vo2max_value}")
    else:
        print("No VO2Max data found")
