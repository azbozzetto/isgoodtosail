# isgoodtosail

# Weather and Tide Analysis for Sailing Conditions

This repository contains Python code that integrates weather forecasting and tide data to evaluate optimal sailing conditions. The application is built using Flask and retrieves data from OpenWeatherMap and the Argentine Naval Hydrographic Service.

## Features

- Fetches and displays real-time weather and tide data.
- Evaluates potential sailing conditions based on weather forecasts and tide predictions.
- Uses Flask to serve the data through a simple web interface.

## Installation

To set up and run this project locally, follow these steps:

### Prerequisites

- Python 3.x
- pip
- ChromeDriver

### Libraries Installation

Run the following commands to install the necessary libraries and tools:

```bash
apt-get update
pip install flask geocoder pandas requests beautifulsoup4 numpy pytz selenium
apt install chromium-chromedriver
cp /usr/lib/chromium-browser/chromedriver /usr/bin
