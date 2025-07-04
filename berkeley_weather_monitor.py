import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import time

class BerkeleyWeatherMonitor:
    def __init__(self):
        # OpenWeatherMap API (free tier)
        self.api_key = os.getenv('OPENWEATHER_API_KEY')  # Get free key from openweathermap.org
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
        # Berkeley, CA coordinates
        self.lat = 37.8715
        self.lon = -122.2730
        
        # Email configuration
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')  # Use app password for Gmail
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # Weather thresholds
        self.temp_threshold = 75  # Fahrenheit
        self.rain_threshold = 0.5  # inches in 24 hours
        
    def get_weather_forecast(self):
        """Get 10-day forecast from OpenWeatherMap One Call API"""
        try:
            # Using One Call API 3.0 for 8-day forecast (closest to 10 days with free tier)
            url = f"{self.base_url}/onecall"
            params = {
                'lat': self.lat,
                'lon': self.lon,
                'appid': self.api_key,
                'units': 'imperial',  # Fahrenheit
                'exclude': 'minutely,alerts'  # Only need daily and hourly
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Error fetching weather data: {e}")
            return None
    
    def analyze_forecast(self, forecast_data):
        """Analyze 8-day forecast for temperature and precipitation alerts"""
        if not forecast_data:
            return []
        
        alerts = []
        
        # Check daily forecasts (up to 8 days available with free tier)
        for day_data in forecast_data['daily']:
            # Convert timestamp to date
            dt = datetime.fromtimestamp(day_data['dt'])
            date_str = dt.strftime('%Y-%m-%d')
            
            # Check temperature (daily max)
            temp_max = day_data['temp']['max']
            if temp_max > self.temp_threshold:
                alerts.append({
                    'type': 'temperature',
                    'date': date_str,
                    'value': temp_max,
                    'message': f"High temperature of {temp_max:.1f}°F expected on {dt.strftime('%A, %B %d')}"
                })
            
            # Check precipitation (daily total)
            daily_rain = 0
            if 'rain' in day_data:
                daily_rain += day_data['rain'] * 0.0393701  # Convert mm to inches
            if 'snow' in day_data:
                daily_rain += day_data['snow'] * 0.0393701  # Include snow as precipitation
            
            if daily_rain > self.rain_threshold:
                alerts.append({
                    'type': 'precipitation',
                    'date': date_str,
                    'value': daily_rain,
                    'message': f"Heavy precipitation expected on {dt.strftime('%A, %B %d')}: {daily_rain:.2f} inches"
                })
        
        # Also check hourly data for next 48 hours for more precise rain alerts
        if 'hourly' in forecast_data:
            hourly_rain = {}
            for hour_data in forecast_data['hourly'][:48]:  # Next 48 hours
                dt = datetime.fromtimestamp(hour_data['dt'])
                date_str = dt.strftime('%Y-%m-%d')
                
                if date_str not in hourly_rain:
                    hourly_rain[date_str] = 0
                
                # Add hourly precipitation
                if 'rain' in hour_data and '1h' in hour_data['rain']:
                    hourly_rain[date_str] += hour_data['rain']['1h'] * 0.0393701
                if 'snow' in hour_data and '1h' in hour_data['snow']:
                    hourly_rain[date_str] += hour_data['snow']['1h'] * 0.0393701
            
            # Check if any day exceeds threshold (using more precise hourly data)
            for date, total_rain in hourly_rain.items():
                if total_rain > self.rain_threshold:
                    dt = datetime.strptime(date, '%Y-%m-%d')
                    # Only add if we don't already have this date from daily data
                    if not any(alert['date'] == date and alert['type'] == 'precipitation' for alert in alerts):
                        alerts.append({
                            'type': 'precipitation',
                            'date': date,
                            'value': total_rain,
                            'message': f"Heavy precipitation expected on {dt.strftime('%A, %B %d')}: {total_rain:.2f} inches (hourly forecast)"
                        })
        
        return alerts
    
    def send_email_alert(self, alerts):
        """Send email notification with weather alerts"""
        if not alerts:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"Berkeley Weather Alert - {datetime.now().strftime('%B %d, %Y')}"
            
            # Create email body
            body = "Weather Alert for Berkeley, CA\n\n"
            body += "The following weather conditions are expected:\n\n"
            
            for alert in alerts:
                body += f"🌡️ {alert['message']}\n"
            
            body += f"\nAlert sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            body += "\nStay safe and plan accordingly!"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, self.recipient_email, text)
            server.quit()
            
            print(f"Alert email sent successfully with {len(alerts)} alerts")
            
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def run_check(self):
        """Run a single weather check"""
        print(f"Checking Berkeley weather for next 8 days at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        forecast_data = self.get_weather_forecast()
        alerts = self.analyze_forecast(forecast_data)
        
        if alerts:
            print(f"Found {len(alerts)} weather alerts")
            self.send_email_alert(alerts)
        else:
            print("No weather alerts needed")
    
    def run_monitoring(self, check_interval_hours=6):
        """Run continuous monitoring"""
        print(f"Starting Berkeley weather monitoring...")
        print(f"Monitoring for: Temperature > {self.temp_threshold}°F, Rain > {self.rain_threshold} inches")
        print(f"Forecast range: Next 8 days (free tier limit)")
        print(f"Check interval: {check_interval_hours} hours")
        
        while True:
            try:
                self.run_check()
                time.sleep(check_interval_hours * 3600)  # Convert hours to seconds
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

# Configuration for deployment
def create_requirements_txt():
    """Create requirements.txt for deployment"""
    requirements = """requests==2.31.0
python-dotenv==1.0.0
"""
    return requirements

def create_env_template():
    """Create environment variables template"""
    env_template = """# Weather API Configuration
OPENWEATHER_API_KEY=your_api_key_here

# Email Configuration
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password_here
RECIPIENT_EMAIL=recipient@gmail.com
"""
    return env_template

def create_github_actions_workflow():
    """Create GitHub Actions workflow for automated monitoring"""
    workflow = """name: Berkeley Weather Monitor

on:
  schedule:
    # Run every 6 hours (adjust as needed)
    - cron: '0 */6 * * *'
  workflow_dispatch: # Allow manual trigger

jobs:
  weather-check:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests python-dotenv
    
    - name: Run weather check
      env:
        OPENWEATHER_API_KEY: ${{ secrets.OPENWEATHER_API_KEY }}
        SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
        SENDER_PASSWORD: ${{ secrets.SENDER_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: python weather_monitor.py
"""
    return workflow

def create_deployment_script():
    """Create deployment script for GitHub Actions"""
    deployment_script = """# GitHub Actions Deployment (FREE!)

## Setup Instructions:

### 1. Create GitHub Repository
1. Create new repository: berkeley-weather-monitor
2. Upload these files:
   - weather_monitor.py
   - .github/workflows/weather-monitor.yml

### 2. Set up Secrets in GitHub
Go to Settings > Secrets and Variables > Actions, add:
- OPENWEATHER_API_KEY: Your OpenWeatherMap API key
- SENDER_EMAIL: Your Gmail address
- SENDER_PASSWORD: Your Gmail app password
- RECIPIENT_EMAIL: Email to receive alerts

### 3. Get API Key (Free)
1. Go to openweathermap.org
2. Sign up for free account
3. Get API key from dashboard

### 4. Set up Gmail App Password
1. Enable 2-factor authentication on Gmail
2. Go to Google Account settings
3. Generate app password for "Mail"
4. Use this password (not your regular password)

### 5. Test & Monitor
- Go to Actions tab in GitHub
- Click "Run workflow" to test
- Check logs to ensure it works
- It will run automatically every 6 hours

## Features:
✅ Completely free hosting on GitHub
✅ Runs automatically every 6 hours
✅ No server maintenance required
✅ Easy to modify schedule in workflow file
✅ View logs in GitHub Actions tab

## File Structure:
berkeley-weather-monitor/
├── weather_monitor.py
├── .github/
│   └── workflows/
│       └── weather-monitor.yml
└── README.md
"""
    return deployment_script

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create and run monitor
    monitor = BerkeleyWeatherMonitor()
    
    # Run single check (perfect for GitHub Actions)
    monitor.run_check()
    
    # Print deployment files for reference
    print("\n" + "="*50)
    print("GITHUB ACTIONS WORKFLOW FILE")
    print("Save as: .github/workflows/weather-monitor.yml")
    print("="*50)
    print(create_github_actions_workflow())
    
    print("\n" + "="*50)
    print("DEPLOYMENT INSTRUCTIONS")
    print("="*50)
    print(create_deployment_script())