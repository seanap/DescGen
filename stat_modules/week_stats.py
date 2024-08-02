from garminconnect import Garmin
import datetime

# Garmin Connect credentials
EMAIL = 'garmin_email'
PASSWORD = 'garmin_pass'

def convert_gap_to_min_per_mile(gap_m_per_s):
    if gap_m_per_s > 0:
        gap_min_per_mile = (1609.34 / gap_m_per_s) / 60
        minutes = int(gap_min_per_mile)
        seconds = int((gap_min_per_mile - minutes) * 60)
        return f"{minutes}:{seconds:02d}"
    else:
        return "0:00"

def convert_cm_to_miles(cm):
    return cm / 160934.0

def convert_milliseconds_to_hours_minutes(milliseconds):
    seconds = milliseconds / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h:{minutes:02d}m"

def convert_centimeters_to_feet(cm):
    return cm / 30.48

def calculate_beers_earned(calories):
    return round(calories / 150, 1)

def get_stats(client, start_date, end_date):
    try:
        distance_summary = client.get_progress_summary_between_dates(start_date, end_date, 'distance')
        elevation_summary = client.get_progress_summary_between_dates(start_date, end_date, 'elevationGain')
        duration_summary = client.get_progress_summary_between_dates(start_date, end_date, 'duration')
        
        total_distance = convert_cm_to_miles(distance_summary[0]['stats']['running']['distance']['sum'])
        total_elevation = elevation_summary[0]['stats']['running']['elevationGain']['sum']
        total_duration_ms = duration_summary[0]['stats']['running']['duration']['sum']
        
        total_duration = convert_milliseconds_to_hours_minutes(total_duration_ms)
        
        activities = client.get_activities_by_date(start_date, end_date)
        
        total_calories = 0
        total_gap = 0
        total_gap_count = 0
        for activity in activities:
            if activity['activityType']['typeKey'] == 'running':
                total_calories += activity['calories']
                if 'avgGradeAdjustedSpeed' in activity:
                    total_gap += activity['avgGradeAdjustedSpeed']
                    total_gap_count += 1
        
        avg_gap = convert_gap_to_min_per_mile(total_gap / total_gap_count if total_gap_count > 0 else 0)
        beers_earned = calculate_beers_earned(total_calories)
        
        return {
            'gap': avg_gap,
            'distance': total_distance,
            'elevation': convert_centimeters_to_feet(total_elevation),
            'duration': total_duration,
            'beers_earned': beers_earned
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        print(f"No stats data found for {start_date} to {end_date}")
        return None

def main():
    client = Garmin(EMAIL, PASSWORD)
    client.login()
    
    today = datetime.datetime.now()
    six_days_ago = today - datetime.timedelta(days=6)
    thirty_days_ago = today - datetime.timedelta(days=30)
    start_of_year = datetime.datetime(today.year, 1, 1)
    
    week_stats = get_stats(client, six_days_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    month_stats = get_stats(client, thirty_days_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    year_stats = get_stats(client, start_of_year.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    
    if week_stats:
        print(f"Week Stats: GAP {week_stats['gap']}, Distance {week_stats['distance']:.2f}mi, Elevation {week_stats['elevation']:.2f}ft, Time {week_stats['duration']}, Beers Earned {week_stats['beers_earned']:.1f}")
    
    if month_stats:
        print(f"Month Stats: GAP {month_stats['gap']}, Distance {month_stats['distance']:.2f}mi, Elevation {month_stats['elevation']:.2f}ft, Time {month_stats['duration']}, Beers Earned {month_stats['beers_earned']:.1f}")
    
    if year_stats:
        print(f"Year Stats: GAP {year_stats['gap']}, Distance {year_stats['distance']:.2f}mi, Elevation {year_stats['elevation']:.2f}ft, Time {year_stats['duration']}, Beers Earned {year_stats['beers_earned']:.1f}")

if __name__ == "__main__":
    main()
