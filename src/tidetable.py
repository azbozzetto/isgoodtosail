#!/usr/bin/env python

# import subprocess
# import sys
# packages = ["flask", "gunicorn", "lxml", "geocoder", "pandas", "requests", "bs4", "numpy", "pytz", "selenium","webdriver_manager"]
# def install(package):
#     subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# for package in packages:
#     try:
#         __import__(package)
#         print(f"{package} is already installed.")
#     except ImportError:
#         print(f"{package} not found, installing...")
#         install(package)

import os
from datetime import datetime
import pandas as pd
import numpy as np
import pytz
import lxml
import geocoder
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

MAREAS_URL = 'http://www.hidro.gob.ar/oceanografia/Tmareas/Form_Tmareas.asp'
PRONOSTICO_URL = 'http://www.hidro.gov.ar/oceanografia/pronostico.asp'

port = 'PUERTO DE BUENOS AIRES (Dársena F)'

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

generate_tide_table('2024','4',port)