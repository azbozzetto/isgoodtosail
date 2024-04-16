#!/bin/bash

# Exit script on any error
set -e

# Update system and install required packages
echo "Updating system and installing required system packages..."
sudo apt-get update && sudo apt-get install -y \
    wget \
    unzip \
    python3-pip \
    python3-dev \
    libpq-dev  # If you're using PostgreSQL

# Install Chrome for Selenium (Optional)
echo "Installing Google Chrome..."
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb || sudo apt-get -f install -y  # install dependencies if needed

# Install ChromeDriver (Check for latest version and compatibility with installed Chrome)
echo "Installing ChromeDriver..."
CHROME_DRIVER_VERSION=`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`
wget https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/chromedriver
sudo chmod +x /usr/local/bin/chromedriver
rm chromedriver_linux64.zip

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
pip3 install -r requirements.txt

echo "Setup completed successfully."
