
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Create a data directory for persistent storage
RUN mkdir -p /app/data

# Create a default casino_chips.json if it doesn't exist
RUN echo '{}' > /app/data/casino_chips.json.default

# Set proper permissions
RUN chmod 755 /app/data

# Run main.py when the container launches
CMD ["python", "main.py"]