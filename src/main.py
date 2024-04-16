# @title Imports and conf

import os
from datetime import datetime

API_KEY = '024f6cfecb6489a8a498fea463be2050'
API_LANG = 'es'
API_UNITS = 'metric'
API_FORECAST_N = '9'

WEATHER_URL = "https://api.openweathermap.org/data/2.5/forecast"
lat = -34.4
lon = -58.5

# Function to fetch weather data
app = Flask(__name__)

@app.route('/')
def fetch_weather():
    params = {
        "lat": lat,
        "lon": lon,
        "lang": API_LANG,
        "units": API_UNITS,
        "appid": API_KEY,
        "cnt": API_FORECAST_N
    }
    response = requests.get(WEATHER_URL, params=params)
    weather_json = response.json()
    weather_df = pd.json_normalize(weather_json, record_path='list')
    timezone = (weather_json['city']['timezone'] / 3600) * 60
    city = weather_json['city']['name']
    timezone = pytz.FixedOffset(timezone)
    weather_df.drop(['pop','dt_txt','visibility','main.pressure','main.temp','main.feels_like','main.temp_min','main.temp_max','main.sea_level','main.grnd_level','main.humidity','main.temp_kf','clouds.all','sys.pod'], axis=1, inplace=True)

    weather_df['datetime'] = pd.to_datetime(weather_df['dt'], unit='s', utc=True)
    weather_df['datetime'] = weather_df['datetime'].dt.tz_convert(timezone)
    weather_df['weather_clouds'] = weather_df['weather'].apply(lambda x: x[0]['description'].upper())
    weather_df['wind_speed_knots'] = round(weather_df['wind.speed'] * 1.94384, 1)
    weather_df['wind_gust_knots'] = round(weather_df.get('wind.gust', 0).fillna(0) * 1.94384, 1)
    weather_df['wind_direction'] = weather_df['wind.deg'].apply(degrees_to_compass)

    return weather_df

#if __name__ == '__main__':
#    port = int(os.environ.get('PORT', 8080))
#    app.run(host='0.0.0.0', port=port, debug=True)
