#!/usr/bin/env python

import os
from datetime import datetime
import json
import pandas as pd
import numpy as np
import pytz
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
import requests

# Setting global variables for API configuration
API_KEY = '024f6cfecb6489a8a498fea463be2050'
API_LANG = 'es'
API_UNITS = 'metric'
API_FORECAST_N = '9'

WEATHER_URL = "https://api.openweathermap.org/data/2.5/forecast"
MAREAS_URL = 'http://www.hidro.gob.ar/oceanografia/Tmareas/Form_Tmareas.asp'
PRONOSTICO_URL = 'http://www.hidro.gov.ar/oceanografia/pronostico.asp'

GOOD_MIN_WIND = 5
GOOD_MAX_WIND = 18
BAD_WEATHER = ['LLUVIA', 'TORMENTA']
MIN_TIDE = 0.4

CSV_PATH = './res/shn_data'

MONTH_NAMES = {
    '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril', '5': 'Mayo',
    '6': 'Junio', '7': 'Julio', '8': 'Agosto', '9': 'Setiembre',
    '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

app = Flask(__name__)

# Utility function to convert degrees to compass direction
def degrees_to_compass(degrees):
    compass_points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    index = int((degrees + 22.5) // 45) % 8
    return compass_points[index]

# Function to fetch weather data
def fetch_weather(latitude, longitude):
    params = {
        "lat": latitude,
        "lon": longitude,
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

# Function to calculate tide height with rule of 12º
def calculate_tide_height_rule_of_twelfths(low_tide_time, low_tide_height, high_tide_time, high_tide_height, forecast_time):
    high_tide_height = float(high_tide_height)
    low_tide_height = float(low_tide_height)
    total_range = high_tide_height - low_tide_height
    total_time = (high_tide_time - low_tide_time).total_seconds() / 3600
    elapsed_time = (forecast_time - low_tide_time).total_seconds() / 3600

    if elapsed_time <= 1:
        tide_increment = total_range * (1/12)
    elif elapsed_time <= 2:
        tide_increment = total_range * (3/12)
    elif elapsed_time <= 4:
        tide_increment = total_range * (6/12)
    elif elapsed_time <= 5:
        tide_increment = total_range * (8/12)
    else:
        tide_increment = total_range * (9/12)

    tide_height = low_tide_height + tide_increment
    return tide_height

# Function to calculate tide height
def calculate_tide_height(forecast_time, tide_df):
    for i in range(len(tide_df) - 1):
        low_tide_time = tide_df.iloc[i]['datetime']
        high_tide_time = tide_df.iloc[i + 1]['datetime']
        low_tide_height = tide_df.iloc[i]['height']
        high_tide_height = tide_df.iloc[i + 1]['height']

        if low_tide_time <= forecast_time <= high_tide_time:
            return calculate_tide_height_rule_of_twelfths(low_tide_time, low_tide_height, high_tide_time, high_tide_height, forecast_time)

    return None

# Function to get tide table csv
def generate_tide_table(year, month, port):
    month_name = MONTH_NAMES[str(month)]
    file_path = f'{CSV_PATH}/{year}/{port}/{month}. tide_{month_name}.csv'
    if not os.path.exists(file_path):
        print(f'No se encontro el archivo{file_path}')
    
    tide_table_df = pd.read_csv(file_path, parse_dates=['datetime'])
    tide_table_df['datetime'] = pd.to_datetime(tide_table_df['datetime']).dt.tz_convert('Etc/GMT+3')
    tide_table_df.loc[:, 'FORECAST'] = False
    
    # Merge with Forecast Tide Data
    data = []
    response = requests.get(PRONOSTICO_URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    table_rows = soup.find_all('tr')

    for row in table_rows:
        # Extract the text from each table cell (td element) in the row
        cells = [cell.get_text(strip=True) for cell in row.find_all('td')]
        data.append(cells)

    # Convert the data into a DataFrame
    tide_df = pd.DataFrame(data, columns=['port','event','Time','height','Date'])
    tide_df = tide_df.dropna()
    tide_df['datetime'] = pd.to_datetime(tide_df['Date'] + ' ' + tide_df['Time'], errors='coerce', format='%d/%m/%Y %H:%M').dt.tz_localize('Etc/GMT+3')
    tide_df.drop(['Date', 'Time'], axis=1, inplace=True)
    tide_df['port'] = tide_df['port'].replace(r'^\s*$', np.nan, regex=True)
    tide_df['port'] = tide_df['port'].ffill()
    
    tide_df['height'] = tide_df['height'].str.replace('m', '').astype(float, errors='ignore')
    tide_df['height'] = tide_df['height'].replace('---', np.NaN)
    tide_df.dropna(subset=['height'], inplace=True)
    tide_df = tide_df.sort_values(by='datetime')

    tide_df.loc[:, 'FORECAST'] = True
    tide_df = tide_df[tide_df['port'] == port]
    tide_df['FORECAST'] = True
    tide_df = tide_df[['datetime','height','FORECAST']]

    tide_table_df = pd.concat([tide_table_df, tide_df], axis=0).sort_values(by='datetime')
    df = tide_table_df
    df.set_index('datetime', inplace=True)
    df['nearby_true'] = df['FORECAST'].rolling('2h', center=True).max().fillna(0).astype(bool)
    df['check'] = ~df['nearby_true']
    filtered_df = df[df['check'] | df['FORECAST']].copy()
    filtered_df.reset_index(inplace=True)
    filtered_df.drop(columns=['nearby_true', 'check'], inplace =True)

    tide_df = filtered_df

    return tide_df

@app.route('/', methods=['POST', 'GET'])
def good_conditions():
    lat = -34.548
    lon = -58.422
    port = 'PUERTO DE BUENOS AIRES (Dársena F)'

    if request.method == 'POST':
        req = request.get_json(force=True)
        parameters = req.get("queryResult", {}).get("parameters", {})

        print("Received a request from Dialogflow:")
        print(json.dumps(req, indent=4))

        # Handling based on the intent name
        intent_name = req.get("queryResult", {}).get("intent", {}).get("displayName", "")
       
        def check_sailing_conditions_specific_location(req):
            lat = parameters.get("latitude", -34.548)
            lon = parameters.get("longitude", -58.422)
            port = parameters.get('port', 'PUERTO DE BUENOS AIRES (Dársena F)')
            response_text = f"En la latitud {lat} y longitud {lon}, las condiciones son adecuadas para navegar hoy."
            return {
                "fulfillmentMessage": response_text
            }
        # Prepare the response for Dialogflow
        if intent_name == "navegar 34 58":
            res = check_sailing_conditions_specific_location(req)
        else:
            res = {
                "fulfillmentMessage": "Lo siento, no entendí eso. ¿Puedes repetirlo?"
            }

    else:
        lat = request.args.get('lat', default=-34.548, type=float)
        lon = request.args.get('lon', default=-58.422, type=float)
        port = request.args.get('port', default='PUERTO DE BUENOS AIRES (Dársena F)', type=str)
    
    forecast_df = fetch_weather(lat,lon)
    forecast_df['IsGood?'] = False
    all_tide_df = pd.DataFrame()

    min_year, min_month = forecast_df['datetime'].min().year, forecast_df['datetime'].min().month
    max_year, max_month = forecast_df['datetime'].max().year, forecast_df['datetime'].max().month

    for year in range(min_year, max_year + 1):
        start_month = min_month if year == min_year else 1
        end_month = max_month if year == max_year else 12
        for month in range(min_month, max_month + 1):
            tide_df = generate_tide_table(str(year), str(month), port)
            all_tide_df = pd.concat([all_tide_df, tide_df])

    forecast_df['tide_height'] = round(forecast_df['datetime'].apply(lambda x: calculate_tide_height(x, all_tide_df)), 2)

    for index, row in forecast_df.iterrows():
        weather_description = row['weather'][0]['description'].upper()
        wind_speed = row['wind_speed_knots']
        wind_gust = row['wind_gust_knots']
        height = row['tide_height']

        if all(word not in weather_description for word in BAD_WEATHER) and GOOD_MIN_WIND <= wind_speed <= GOOD_MAX_WIND and wind_gust <= GOOD_MAX_WIND and MIN_TIDE <= height:
            forecast_df.at[index, 'IsGood?'] = True

    forecast_df = forecast_df[['datetime', 'IsGood?', 'weather_clouds', 'wind_direction', 'wind_speed_knots', 'wind_gust_knots', 'tide_height']]
    forecast_df['datetime'] = forecast_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')    
    
    if request.method == 'POST':
        forecast_df = forecast_df[forecast_df['IsGood?'] == True]
        
    json_df = forecast_df.to_json(orient='records')
    json_out = json.loads(json_df)

    if request.method == 'GET':
        res = { 'data: ':json_out, 
                    'method ': request.method, 
                    'lat ':lat, 
                    'lon ': lon, 
                    'port:': port
                }

    return jsonify(res)

if __name__ == '__main__':
    hostport = int(os.environ.get('PORT', 8080))
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app.run(host='0.0.0.0', port=hostport, debug=False)