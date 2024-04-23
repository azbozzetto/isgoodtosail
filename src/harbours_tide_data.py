#!/usr/bin/env python

import subprocess
import sys
packages = ["pandas", "requests", "bs4", "numpy", "selenium"]
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for package in packages:
    try:
        __import__(package)
        print(f"{package} is already installed.")
    except ImportError:
        print(f"{package} not found, installing...")
        install(package)

import os
import re
import json
from datetime import datetime
from dateutil import parser
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from io import StringIO

MAREAS_URL = 'http://www.hidro.gob.ar/oceanografia/Tmareas/Form_Tmareas.asp'

# Set up Selenium to use Chrome in headless mode
CHROME_OPTIONS = Options()
CHROME_OPTIONS.headless = True
CHROME_OPTIONS.binary_location = "/usr/bin/chromium-browser"  #"/usr/bin/chromium"
CHROME_OPTIONS.add_argument("--headless")                     # Important for headless servers
CHROME_OPTIONS.add_argument("--no-sandbox")                   # Bypass OS security model
CHROME_OPTIONS.add_argument("--disable-dev-shm-usage")        # Overcome limited resource problems
CHROME_OPTIONS.add_argument("--disable-gpu")                  # Applicable if GPU acceleration isn't available
CHROME_OPTIONS.add_argument("--window-size=1920x1080")        # Set window size if needed

CSV_PATH = 'src/res/shn_data/'
MONTH_NAMES = {
        '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril', '5': 'Mayo',
        '6': 'Junio', '7': 'Julio', '8': 'Agosto', '9': 'Setiembre',
        '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }

def parse_coordinates(harbour):
    driver = webdriver.Chrome(options=CHROME_OPTIONS)
    harbours_data = {}
    year = datetime.now().year
    month = MONTH_NAMES[str(datetime.now().month)]

    def convert_to_decimal(degrees, minutes, direction):
        decimal_degrees = round(degrees + (minutes / 60),3)
        if direction in ['S', 'W']:
            decimal_degrees *= -1
        return decimal_degrees

    try:
        driver.get(MAREAS_URL)
        WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.NAME, 'FAnio')))
        Select(driver.find_element(By.NAME, 'FAnio')).select_by_visible_text(str(year))
        Select(driver.find_element(By.NAME, 'Localidad')).select_by_visible_text(harbour)
        Select(driver.find_element(By.NAME, 'FMes')).select_by_visible_text(month)
        driver.find_element(By.NAME, 'B1').click()
        WebDriverWait(driver, 3).until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'tablasdemarea')))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        panel_bodies = soup.find_all('div', {'class': 'panel-body'})
        target_coord = soup.find('div', {'class': 'col-md-8 col-md-offset-2'})
        paragraphs = target_coord.find_all('p')

        try:
            pattern = r"Lat\.\s*(\d+)º\s*(\d+)' (\w)\s*Long\.\s*(\d+)º\s*(\d+)' (\w)"
            match = re.search(pattern, paragraphs[1].text)

            if match:
                lat = convert_to_decimal(float(match.group(1)),float(match.group(2)),str(match.group(3)))
                lon = convert_to_decimal(float(match.group(4)),float(match.group(5)),str(match.group(6)))
                harbours_data[harbour] = {'latitude': lat, 'longitude': lon}

            else:
                raise ValueError("Latitude and longitude not found in text")

        except:
            return None
        
    finally:
        driver.quit()

    try:
        with open(f'{CSV_PATH}/harbours_data.json', 'r', encoding='utf-8') as file:
            harbours_file = json.load(file)
    except FileNotFoundError:
        harbours_file = {}

    harbours_file.update(harbours_data)

    # Write the updated dictionary back to the file
    with open(f'{CSV_PATH}/harbours_data.json', 'w', encoding='utf-8') as file:
        json.dump(harbours_file, file, ensure_ascii=False, indent=4)

    return harbours_data

def generate_tide_table(year, month, harbour):    
    driver = webdriver.Chrome(options=CHROME_OPTIONS)
    harbours_data = {}
    tide_table_df = pd.DataFrame()
    table_dfs = []
    
    try:
        month_number = next((k for k, v in MONTH_NAMES.items() if v == month), None)

        driver.get(MAREAS_URL)
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.NAME, 'FAnio')))
        Select(driver.find_element(By.NAME, 'FAnio')).select_by_visible_text(str(year))
        Select(driver.find_element(By.NAME, 'Localidad')).select_by_visible_text(harbour)
        Select(driver.find_element(By.NAME, 'FMes')).select_by_visible_text(month)
        driver.find_element(By.NAME, 'B1').click()
        WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'tablasdemarea')))
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, 'table')))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        panel_bodies = soup.find_all('div', {'class': 'panel-body'})

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
            table_html = StringIO(str(table))
            table_df = pd.read_html(table_html)[0]
            table_dfs.append(table_df)

        # Concatenate all the DataFrames in the list to create the combined DataFrame
        tide_table_df = pd.concat(table_dfs, ignore_index=True)

        tide_table_df['DIA'] = tide_table_df['DIA'].ffill().astype(int)
        tide_table_df['datetime'] = pd.to_datetime(tide_table_df['DIA'].astype(str) + '/' + month_number + '/' + year + ' ' + tide_table_df['HORA:MIN'], format='%d/%m/%Y %H:%M').dt.tz_localize('Etc/GMT+3')
        tide_table_df.drop(['DIA', 'HORA:MIN'], axis=1, inplace=True)
        tide_table_df = tide_table_df[['datetime','ALTURA (m)']]
        tide_table_df = tide_table_df.rename(columns={'ALTURA (m)': 'height'})
        tide_table_df['harbour'] = harbour

    finally:
        driver.quit()

    return tide_table_df

if __name__ == '__main__':
    harbours = []
    years = []
    months = []
    driver = webdriver.Chrome(options=CHROME_OPTIONS)
    try:
        driver.get(MAREAS_URL)
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.NAME, 'FAnio')))    
        port_list = Select(driver.find_element(By.NAME, 'Localidad'))
        harbours = [option.text for option in port_list.options]
        # year_list = Select(driver.find_element(By.NAME, 'FAnio'))
        # years = [option.text for option in year_list.options]
        years = ['2024']
        month_list = Select(driver.find_element(By.NAME, 'FMes'))
        months = [option.text for option in month_list.options]

    finally:
        driver.quit()

    for harbour in harbours:
        harbour_data = parse_coordinates(harbour)
        print(harbour, harbour_data)
        for year in years:
            for month in months:
                month_number = next((k for k, v in MONTH_NAMES.items() if v == month), None)
                directory_path = f'{CSV_PATH}/{year}/{harbour}'
                file_path = os.path.join(directory_path, f'{month_number}. tide_{month}.csv')

                if not os.path.exists(directory_path):
                    os.makedirs(directory_path)

                if os.path.exists(file_path):
                    continue
                else:
                    generate_tide_table(year,month,harbour).to_csv(file_path, index=False)
