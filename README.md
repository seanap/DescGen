# Auto-Strava-Stat-Description
Automatically set your strava description with fun stats from Strava, Garmin, Smashrun, Intervals.icu, and WeatherAPI.  
To automate updating your Strava activity descriptions with your running stats, this will use the Strava API and Python. Below is a step-by-step guide.
```
🏆 284 days in a row
🌡️ Misery Index: 121.7 😀 Pleasant running conditions
🏅 during sunrise
🏅 fastest 7mi ever
🏅 fastest 12k ever
🏅 coolest run in 3 months
🏅 best performance in a month
🏅 highest avg cadence in a month
🏅 New best power: 317W for 1hr
🏅 New best pace: 53m7s for 10km
🍺 Beers Earned: 5.4
🏋️ 59 | 💦 64 | 🗿 -10% | 🦾 Optimal
❤️‍🔥 53 | ⚡ 321W | 💼 1252 kJ | ⚡/❤️ 2.13

7️⃣ Past 7 days:
🏃 9:00 | 🗺️ 42.0 | 🏔️ 3418' | 🕓 6h:30m | 🍺 30
📅 Past 30 days:
🏃 9:23 | 🗺️ 186 | 🏔️ 16099' | 🕓 30h:01m | 🍺 139
🌍 This Year:
🏃 9:48 | 🗺️ 918 | 🏔️ 80171' | 🕓 162h:51m | 🍺 726
```
### Data Sources
```
[Smashrun Longest Streak] 
[WeatherAPI calculation] : [preset range] 
[Smashrun Noteables]
[ICU Achievements]
[Garmin Calories / 150] 
[ICU: Fitness | Fatigue | Form | Form % Description]
[Garmin vo2max] | [ICU Normalized Power] | [ICU Work] | [ICU Efficency (Power/HR)]

[Garmin Historical Data: trailing 7day, trailing 30 days, current year to date]
[Garmin: GAP | Total Running Miles | Total Elevation | Total Time | Total Calories/150 ]
```
## Step-by-Step Guide:
### 1. Set Up Strava API Access: 
* Create a Strava API application https://www.strava.com/settings/api
* Set up AUTHORIZATION CALL BACK DOMAAIN
  * use localhost if you are just testing locally. For example: http://localhost:5000.
* Note down your Client ID, Client Secret, and Access Token.

### 2. Install Required Python Libraries:
``` bash
pip install requests garminconnect pytz logging dateutil
```
### 3. Prepare the Python Script:
* Download this repo locally `C:/scripts/`
* Replace 'your_client_id', 'your_client_secret', 'your_access_token', and 'your_refresh_token' with your actual Strava API credentials in the main script & stat_modules
* Get USER LEVEL AUTHENTICATION from smashrun: https://api.smashrun.com/v1/documentation and replce with your access token in `notables.py`
* Get your Intervals.icu API key and Athlete ID from your Settings page, and modify `intervals_data.py`
* Get a free WeatherAPI access https://www.weatherapi.com/ and replace you API Key in `misery_index.py`

### 4. Run the Script:
To schedule your script to run every 10 minutes between 4 AM and 10 PM on Windows 11, you can use the Task Scheduler. Here’s how to set it up:
#### Step 1: Open Task Scheduler
  * Press Win + S to open the search bar, type "Task Scheduler," and hit Enter.
  * In the Task Scheduler window, click on "Create Task" on the right-hand side.
#### Step 2: Create a New Basic Task
  * Name the Task: Give your task a name, like "Run Strava Script."
  * Description: (Optional) Provide a description, like "Runs the Strava update script every 10 minutes."
#### Step 3: Trigger the Task
  * Trigger: Select "Daily" and click "Next."
  * Start Date: Set the date and time to start at 4:00 AM.
  * Repeat: On the "Daily" trigger screen, check "Repeat task every" and set it to 10 minutes. Set the "for a duration of" option to 18 hours (from 4:00 AM to 10:00 PM).
  * Advanced Settings: Ensure the task is set to expire at 10:00 PM by specifying the duration of 18 hours.
#### Step 4: Action
  * Action: Select "Start a program" and click "Next."
  * Program/Script: Browse to your Python executable (python.exe).
  * Add Arguments: Add the path to your script, like C:\scripts\main_strava_update.py.
  * Start in: Enter the directory where your script is located (e.g., C:\scripts).
#### Step 5: Finish and Save
  * Review the settings, then click "Finish" to save the task.
  * If prompted, enter your Windows account password to allow the task to run.

## Misery Index
* https://wildstar84.wordpress.com/2013/06/30/the-misery-index-calculating-how-miserable-your-summer-workout-will-be/
* “Misery Index” = (temperature°F + ((dew-point°F * 2) + humidity) / 3) – (windspeed-mph * (1 – (%humidity / 100)))
```
😭Misery Index: {less than 130} {😀 Perfect conditions for a run!}
😭Misery Index: {130-140} {😅 Mildly Uncomfortable - Not too bad for a decent workout}
😭Misery Index: {140-145} {😓 Moderately Uncomfortable}
😭Misery Index: {145-150} {😰 Very Uncomfortable}
😭Misery Index: {150-155} {🥵 Oppressive - Difficult to accomplish much}
😭Misery Index: {155-160} {😡 Miserable - Why??}
😭Misery Index: {160+} {☠️⚠️ Un-doable due to a high risk of heat-exhaustion}
```

## Intervals.icu
* This will grab today's Fitness, Fatigue, and Form values
```
# Fitness | Fatigue | Form | Form Class
  🏋️ 50 | 💦 65 | 🗿 -30% | 🦾 Optimal

# Determine form_class based on form value
Form {20+} {❄️ Too Light}
Form {20 - 5} {🏁 Fresh}
Form {5 - -10} {⛔ Grey Zone}
Form {-10 - -30} {🦾 Optimal}
Form {less than -30} {⚠️ High Risk}
```
