# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# RUN pip install --requirement requirements.txt
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container at /app
COPY src/ /app/src/
COPY res/ /app/res/
RUN ls -la /app/src/
RUN ls -la /app/res/  


# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
#ENV NAME World

# Run main.py when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
