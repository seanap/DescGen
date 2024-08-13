import requests
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Intervals.icu API credentials
INTERVALS_API_KEY = 'icu_api_key'
USER_ID = 'icu_cuser_id'

def get_intervals_data():
    # Set today's date in ISO-8601 format
    today = datetime.today().strftime('%Y-%m-%d')

    # API URL
    url = f"https://intervals.icu/api/v1/athlete/{USER_ID}/wellness/{today}"

    # HTTP Basic Authentication (username is "API_KEY", password is the actual API key)
    auth = ('API_KEY', INTERVALS_API_KEY)

    try:
        # Send GET request to fetch wellness data
        response = requests.get(url, auth=auth)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse JSON response
        data = response.json()

        # Extract Fitness (ctl), Fatigue (atl)
        fitness_raw = data['ctl']
        fatigue_raw = data['atl']

        # Calculate Form (tsb) before rounding
        form_raw = ((fitness_raw - fatigue_raw) / fitness_raw) * 100

        # Round the values for output
        fitness = int(round(fitness_raw))
        fatigue = int(round(fatigue_raw))
        form = int(round(form_raw))

        # Determine form_class based on form value
        if form < -30:
            form_class = "⚠️ High Risk"
        elif -30 <= form <= -10:
            form_class = "🦾 Optimal"
        elif -10 < form <= 5:
            form_class = "⛔ Grey Zone"
        elif 5 < form <= 20:
            form_class = "🏁 Fresh"
        else:
            form_class = "❄️ Too Light"

        # Create a single output value for easy integration
        icu = f"🏋️ {fitness} | 💦 {fatigue} | 🗿 {form}% | {form_class}"

        return icu

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
    return None

if __name__ == "__main__":
    icu = get_intervals_data()
    if icu:
        print(icu)
