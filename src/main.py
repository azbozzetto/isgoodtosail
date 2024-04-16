
# @title Imports and conf

import subprocess
import sys
import os

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

packages = ["flask", "geocoder", "pandas", "requests", "bs4", "numpy", "pytz", "selenium","webdriver_manager"]

for package in packages:
    try:
        __import__(package)
        print(f"{package} is already installed.")
    except ImportError:
        print(f"{package} not found, installing...")
        install(package)

# !apt install chromium-chromedriver

import geocoder
import pandas as pd
import numpy as np
import requests
import pytz
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, request, jsonify

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

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

# Set up Selenium to use Chrome in headless mode
CHROME_OPTIONS = Options()

CHROME_OPTIONS.binary_location = "/usr/bin/chromium-browser"  #"/usr/bin/chromium"
CHROME_OPTIONS.add_argument("--headless")                     # Important for headless servers
CHROME_OPTIONS.add_argument("--no-sandbox")                   # Bypass OS security model
CHROME_OPTIONS.add_argument("--disable-dev-shm-usage")        # Overcome limited resource problems
CHROME_OPTIONS.add_argument("--disable-gpu")                  # Applicable if GPU acceleration isn't available
CHROME_OPTIONS.add_argument("--window-size=1920x1080")        # Set window size if needed
# CHROME_OPTIONS.add_argument("--verbose")
# CHROME_OPTIONS.add_argument("--log-path=chromedriver.log")
     

# @title functions

# Utility function to convert degrees to compass direction
def degrees_to_compass(degrees):
    compass_points = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    index = int((degrees + 22.5) // 45) % 8
    return compass_points[index]

# Function to get current latitude and longitude
def get_current_location():
    g = geocoder.ip('me')
    print(g)
    return round(g.latlng[0], 2), round(g.latlng[1], 2)

# Function to fetch weather data
def fetch_weather(lat, lon):
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

# Function to generate tide table using Selenium
def generate_tide_table(year, month, port):
    MONTH_NAMES = {
        '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril', '5': 'Mayo',
        '6': 'Junio', '7': 'Julio', '8': 'Agosto', '9': 'Septiembre',
        '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    month_name = MONTH_NAMES[str(month)]

    driver = webdriver.Chrome(options=CHROME_OPTIONS)
    try:
        driver.get(MAREAS_URL)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.NAME, 'FAnio')))
        Select(driver.find_element(By.NAME, 'FAnio')).select_by_visible_text(str(year))
        Select(driver.find_element(By.NAME, 'Localidad')).select_by_visible_text(port)
        Select(driver.find_element(By.NAME, 'FMes')).select_by_visible_text(month_name)
        driver.find_element(By.NAME, 'B1').click()
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'tablasdemarea')))
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'table')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        panel_bodies = soup.find_all('div', {'class': 'panel-body'})

        # Initialize an empty DataFrame to store the combined table data
        tide_table_df = pd.DataFrame()
        table_dfs = []

        # Loop through each panel-body and extract the table data
        for panel_body in panel_bodies:
            # Find the table within the panel-body
            table = panel_body.find('table', {'class': 'table table-striped'})
            if table:
                # Find all tr elements in the table
                tr_elements = table.find_all('tr')
                for tr in tr_elements:
                    # Find all td elements in the row
                    td_elements = tr.find_all('td')
                    # Check if the row has at least 3 columns
                    if len(td_elements) >= 3:
                        # Replace commas with dots in the text of the third column (index 2)
                        if td_elements[2].string:
                            td_elements[2].string.replace_with(td_elements[2].string.replace(',', '.'))

            # Convert the table HTML to a DataFrame
            table_df = pd.read_html(str(table))[0]
            table_dfs.append(table_df)

        # Concatenate all the DataFrames in the list to create the combined DataFrame
        tide_table_df = pd.concat(table_dfs, ignore_index=True)

        tide_table_df['DIA'] = tide_table_df['DIA'].fillna(method='ffill').astype(int)
        tide_table_df['datetime'] = pd.to_datetime(tide_table_df['DIA'].astype(str) + '/' + month + '/' + year + ' ' + tide_table_df['HORA:MIN'], format='%d/%m/%Y %H:%M').dt.tz_localize('Etc/GMT+3')
        tide_table_df.drop(['DIA', 'HORA:MIN'], axis=1, inplace=True)
        tide_table_df = tide_table_df[['datetime','ALTURA (m)']]
        tide_table_df = tide_table_df.rename(columns={'ALTURA (m)': 'height'})
        tide_table_df.loc[:, 'FORECAST'] = False

        # Merge with Forecast Tide Data
        data = []
        response = requests.get(PRONOSTICO_URL)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the data you're interested in
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

        tide_df['port'].replace(r'^\s*$', np.nan, regex=True, inplace=True)

        tide_df['port'].ffill(inplace=True)
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

    finally:
        driver.quit()

    return tide_df

if 'app' not in globals():
    app = Flask(__name__)

    @app.route('/', methods=['POST'])
    def good_conditions():
        #lat = float(request.args.get_json('lat', default=-34.56))
        #lon = float(request.args.get_json('lon', default=-58.40))
        lat = -34.56
        lon = -58.40

        port = 'PUERTO DE BUENOS AIRES (Dársena F)'
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
        json = forecast_df.to_json(orient='records', lines=True, compression='gzip')
        return "Hello" #jsonify(json)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True)
#    app.run(host='0.0.0.0', port=port, debug=True)
