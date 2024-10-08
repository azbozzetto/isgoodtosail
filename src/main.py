#!/usr/bin/env python

import os
import subprocess
import sys

# def install_requirements():
#     if os.path.exists('requirements.txt'):
#         try:
#             subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
#         except subprocess.CalledProcessError as e:
#             print(f"Error installing packages: {e}")
#             sys.exit(1)
            
# install_requirements()

from datetime import datetime
import json
import pandas as pd
import numpy as np
import pytz
from bs4 import BeautifulSoup
# from dialogflow_fulfillment import QuickReplies, WebhookClient, Text, Card, Payload, RichResponse
from typing import Dict
from flask import Flask, request, jsonify
import traceback
import requests
from dotenv import load_dotenv

# Setting global variables for API configuration
load_dotenv()
API_KEY = os.getenv('API_KEY')
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

    # Utility function to convert degrees to compass direction
    def degrees_to_compass(degrees):
        compass_points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
        index = int((degrees + 22.5) // 45) % 8
        return compass_points[index]
    
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
    weather_df['wind_gust_knots'] = round(weather_df['wind.gust'].ffill() * 1.94384, 1)
    weather_df['wind_direction'] = weather_df['wind.deg'].apply(degrees_to_compass)

    return weather_df

# Function to calculate tide height
def calculate_tide_height(forecast_time, tide_df):
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

    for i in range(len(tide_df) - 1):
        low_tide_time = tide_df.iloc[i]['datetime']
        high_tide_time = tide_df.iloc[i + 1]['datetime']
        low_tide_height = tide_df.iloc[i]['height']
        high_tide_height = tide_df.iloc[i + 1]['height']

        if low_tide_time <= forecast_time <= high_tide_time:
            return calculate_tide_height_rule_of_twelfths(low_tide_time, low_tide_height, high_tide_time, high_tide_height, forecast_time)

    return None

# Function to get tide table csv
def generate_tide_table(year, month, harbour):
    month_name = MONTH_NAMES[str(month)]
    file_path = f'{CSV_PATH}/{year}/{harbour}/{month}. tide_{month_name}.csv'
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
    tide_df = pd.DataFrame(data, columns=['harbour','event','Time','height','Date'])
    tide_df = tide_df.dropna()
    tide_df['datetime'] = pd.to_datetime(tide_df['Date'] + ' ' + tide_df['Time'], errors='coerce', format='%d/%m/%Y %H:%M').dt.tz_localize('Etc/GMT+3')
    tide_df.drop(['Date', 'Time'], axis=1, inplace=True)
    tide_df['harbour'] = tide_df['harbour'].replace(r'^\s*$', np.nan, regex=True)
    tide_df['harbour'] = tide_df['harbour'].ffill()
    
    tide_df['height'] = tide_df['height'].str.replace('m', '').astype(float, errors='ignore')
    tide_df['height'] = tide_df['height'].replace('---', np.nan)
    tide_df.dropna(subset=['height'], inplace=True)
    tide_df = tide_df.sort_values(by='datetime')

    tide_df.loc[:, 'FORECAST'] = True
    tide_df = tide_df[tide_df['harbour'] == harbour]
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


@app.route('/', methods=['GET'])
def good_conditions():
    lat = -34.548
    lon = -58.422
    harbour = 'PUERTO DE BUENOS AIRES (Dársena F)'
    
    forecast_df = fetch_weather(lat,lon)
    forecast_df['IsGood?'] = False
    all_tide_df = pd.DataFrame()

    min_year, min_month = forecast_df['datetime'].min().year, forecast_df['datetime'].min().month
    max_year, max_month = forecast_df['datetime'].max().year, forecast_df['datetime'].max().month

    for year in range(min_year, max_year + 1):
        start_month = min_month if year == min_year else 1
        end_month = max_month if year == max_year else 12
        for month in range(min_month, max_month + 1):
            tide_df = generate_tide_table(str(year), str(month), harbour)
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

    json_res = json.loads(forecast_df.to_json(orient='records'))

    return jsonify({'Lat / Lon': f'{lat} / {lon}',
                    'Puerto':harbour,
                    'Data': json_res})


# def handler(agent: WebhookClient) -> None: 
#     agent.add('Vas a navegar en:')
#     agent.add(QuickReplies(quick_replies=['PUERTO DE BUENOS AIRES (Dársena F)', 'SAN FERNANDO']))

# def welcome_handler(agent):
#     agent.add('Hola!')
#     agent.add('¿Como puedo ayudarte?')

# def fallback_handler(agent):
#     agent.add('Sorry, I missed what you said.')
#     agent.add('Can you say that again?')

result_df = None

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
            global result_df
            # Step 1: Fetch parameters from the request object
            request_json = request.get_json(silent=True, force=True)
            query_result = request_json.get('queryResult')
            query_text = query_result.get('queryText')
            parameters = query_result.get('parameters')          
            location = parameters.get('city')
            
            # Step 2:  Extract details from BigQuery
            if location:
                print(query_text)
                result_df = good_conditions(query_text)
                print(result_df)

            # Step 3:  Let's see how we can build a CARD response for Dialogflow
            agent = WebhookClient(request_json) # Build Agent response object
            agent.handle_request(handler)
            return agent.response

    except Exception as e:
        print(str(e))
        print(traceback.print_exc())


if __name__ == '__main__':  
    port = int(os.environ.get('PORT', 8080))
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app.run(host='0.0.0.0', port=port, debug=True)