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

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
