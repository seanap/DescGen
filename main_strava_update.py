import requests
import datetime
import pytz
import logging
from garminconnect import Garmin
from dateutil import parser as date_parser
from stat_modules.misery_index import get_misery_index
from stat_modules import streak, beers_earned, vo2max, week_stats
from strava_utils import refresh_access_token, get_recent_activities, get_activity_details
from stat_modules.smashrun import get_notables
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Strava API credentials
CLIENT_ID = 'your_id'
CLIENT_SECRET = 'your_secret'
REFRESH_TOKEN = 'your_token'
ACCESS_TOKEN = 'your_token'
GARMIN_EMAIL = 'garmin_email'
GARMIN_PASSWORD = 'Garmin_pass'

# Log file to track processed activities
LOG_FILE = "processed_activities.log"

def log_activity(activity_id):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{activity_id}\n")

def is_activity_processed(activity_id):
    if not os.path.exists(LOG_FILE):
        return False
    
    with open(LOG_FILE, 'r') as log_file:
        processed_ids = log_file.read().splitlines()
    
    return activity_id in processed_ids

# Function to refresh Strava access token
def refresh_access_token():
    global ACCESS_TOKEN  # Ensure this is updated globally
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
        logging.info("Access token refreshed")
    else:
        logging.error(f"Error refreshing access token: {response_data}")

# Function to update the activity description
def update_activity_description(activity_id, description):
    global ACCESS_TOKEN  # Ensure that the latest token is being used
    response = requests.put(
        f'https://www.strava.com/api/v3/activities/{activity_id}',
        headers={'Authorization': f'Bearer {ACCESS_TOKEN}'},
        data={'description': description}
    )
    if response.status_code == 401:  # Token expired, refresh and retry
        logging.error("Access token expired, refreshing...")
        refresh_access_token()
        response = requests.put(
            f'https://www.strava.com/api/v3/activities/{activity_id}',
            headers={'Authorization': f'Bearer {ACCESS_TOKEN}'},
            data={'description': description}
        )
    if response.status_code != 200:
        logging.error(f"Error updating activity: {response.text}")
    return response.json()

# Main function to update the description of the most recent activity
def main(force_update=False):
    refresh_access_token()

    # Log the refreshed token for debugging purposes
    global ACCESS_TOKEN
    logging.info(f"Refreshed Access Token: {ACCESS_TOKEN}")

    activities = get_recent_activities()
    if not activities:
        logging.info("No activities found")
        return

    latest_activity = activities[0]
    latest_activity_id = latest_activity['id']

    # Calculate the Misery Index using the latest activity
    misery_index, misery_index_description = get_misery_index()
    # Format the Misery Index with the description
    misery_index_formatted = f"🌡️ Misery Index: {misery_index} {misery_index_description}"

    # Get detailed activity data
    detailed_activity = get_activity_details(latest_activity_id)
    logging.info(f"Detailed Activity: {detailed_activity}")

    # Check if the activity has already been processed
    if not force_update and is_activity_processed(latest_activity_id):
        logging.info(f"Activity {latest_activity_id} has already been processed. Skipping...")
        return

    latest_activity_start_date = date_parser.isoparse(latest_activity['start_date'])

    if not force_update:
        last_checked = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=10)
        if latest_activity_start_date < last_checked:
            logging.info("No new activities to update")
            return

    # Define date ranges for stats
    today = datetime.datetime.now()
    seven_days_ago = today - datetime.timedelta(days=6)
    thirty_days_ago = today - datetime.timedelta(days=29)
    first_day_of_year = datetime.datetime(today.year, 1, 1)

    # Instantiate Garmin client
    client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    client.login()

    # Get stats from modules
    run_streak = streak.get_streak(ACCESS_TOKEN)
    beers = beers_earned.calculate_beers(detailed_activity)  # Ensure correct data passed here
    logging.info(f"Calculated Beers: {beers:.1f}")  # Log calculated beers
    vo2 = vo2max.get_vo2max()
    week = week_stats.get_stats(client, seven_days_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    month = week_stats.get_stats(client, thirty_days_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    year = week_stats.get_stats(client, first_day_of_year.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))

    # Get notables from Smashrun
    notables = get_notables()
    if notables:
        notables_formatted = "\n".join([f"🏅 {notable}" for notable in notables])
    else:
        notables_formatted = ""

    # Safely get stats or fallback to defaults
    month_gap = month.get('gap', 'N/A') if month else 'N/A'
    month_distance = month.get('distance', 0.0) if month else 0.0
    month_elevation = month.get('elevation', 0.0) if month else 0.0
    month_duration = month.get('duration', 'N/A') if month else 'N/A'
    month_beers_earned = month.get('beers_earned', 0.0) if month else 0.0

    year_gap = year.get('gap', 'N/A') if year else 'N/A'
    year_distance = year.get('distance', 0.0) if year else 0.0
    year_elevation = year.get('elevation', 0.0) if year else 0.0
    year_duration = year.get('duration', 'N/A') if year else 'N/A'
    year_beers_earned = year.get('beers_earned', 0.0) if year else 0.0

    # Create description
    description = (
        f"🏆 {run_streak} days in a row\n"
        f"{misery_index_formatted}\n"
        f"{notables_formatted}\n"
        f"🍺 Beers Earned: {beers:.1f}\n"
        f"❤️‍🔥 Vo2Max: {vo2}\n\n"
        f"7️⃣ Week:\n"
        f"🏃 {week['gap']} | 🗺️ {week['distance']:.1f} | 🏔️ {int(week['elevation'])}' | 🕓 {week['duration']} | 🍺 {week['beers_earned']:.0f}\n\n"
        f"📅 Month:\n"
        f"🏃 {month_gap} | 🗺️ {month_distance:.0f} | 🏔️ {int(month_elevation)}' | 🕓 {month_duration} | 🍺 {month_beers_earned:.0f}\n\n"
        f"🌍 Year:\n"
        f"🏃 {year_gap} | 🗺️ {year_distance:.0f} | 🏔️ {int(year_elevation)}' | 🕓 {year_duration} | 🍺 {year_beers_earned:.0f}\n\n"
    )

    # Update Strava activity description
    update_activity_description(latest_activity_id, description)
    
    # Log the activity as processed
    log_activity(latest_activity_id)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Update Strava activity description with stats.")
    parser.add_argument("-f", "--force", action="store_true", help="Force update the most recent activity.")
    args = parser.parse_args()

    main(force_update=args.force)
