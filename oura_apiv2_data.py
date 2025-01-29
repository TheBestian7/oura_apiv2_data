import json
import configparser
import time
import datetime
import requests
import sqlite3
from requests_oauthlib import OAuth2Session

class OuraDataHandler:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Paths
        self.db_file = self.config['PATHS']['db_file']
        self.token_file = self.config['PATHS']['token_file']

        # Secrets
        self.client_id = self.config['SECRETS']['client_id']
        self.client_secret = self.config['SECRETS']['client_secret']

        # Timeframe
        self.start_date = datetime.datetime.strptime(self.config['DBVALUES']['start_date'], '%Y-%m-%d').date()
        end_date = self.config['DBVALUES'].get('end_date', None)
        self.end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else datetime.date.today()
        
        # URLs
        self.callback_url = self.config['URL']['callback_url']
        self.auth_url = self.config['URL']['authorization_url']
        self.token_url = self.config['URL']['token_url']
        self.urls = {
            'daily_activity': self.config['URL']['daily_activity_url'],
            'daily_cardiovascular_age': self.config['URL']['daily_cardiovascular_age'],
            'daily_readiness': self.config['URL']['daily_readiness_url'],
            'daily_resilience': self.config['URL']['daily_resilience_url'],
            'daily_sleep': self.config['URL']['daily_sleep_url'],
            'daily_spo2': self.config['URL']['daily_spo2_url'],
            'daily_stress': self.config['URL']['daily_stress_url'],
            'enhanced_tag': self.config['URL']['enhanced_tag_url'],
            'restmode_period': self.config['URL']['restmode_period_url'],
            'ring_configuration': self.config['URL']['ring_configuration_url'],
            'sessions': self.config['URL']['sessions_url'],            
            'sleep': self.config['URL']['sleep_url'],
            'sleep_time': self.config['URL']['sleep_time_url'],
            'vo2max': self.config['URL']['vo2max_url'],
            'workout': self.config['URL']['workout_url']
        }
   
    def read_token(self):
        # Read token if file exists
        try:
            with open(self.token_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return None

    def save_token(self, token):
        # Save token if necessary
        with open(self.token_file, 'w') as file:
            json.dump(token, file)

    def get_token(self):
        ''' 
        Use the token if available and up-to-date.
        If available but outdated, use the refresh token to update.
        If no token is available, authorize with Oura and save the token.
        '''
        token = self.read_token()
        if not token:
            oauth = OAuth2Session(self.client_id, redirect_uri=self.callback_url)
            authorization_url, _ = oauth.authorization_url(self.auth_url)
            print('Please follow this link and authorize the application:', authorization_url)
            authorization_response = input('Enter the full URL you receive after authorization: ')
            token = oauth.fetch_token(self.token_url, authorization_response=authorization_response, client_secret=self.client_secret)
            self.save_token(token)
        else:
            if token.get('expires_at', 0) < time.time():
                oauth = OAuth2Session(self.client_id, token=token)
                token = oauth.refresh_token(self.token_url, client_id=self.client_id, client_secret=self.client_secret)
                self.save_token(token)
        return token

    def fetch_data(self, data_type):
        # Fetch data for the period specified in config.ini from Oura for self.urls
        if data_type not in self.urls:
            raise ValueError(f"Invalid data type: {data_type}")
        
        token = self.get_token()
        headers = {'Authorization': f"Bearer {token['access_token']}"}
        params = {
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d')
        }
        response = requests.get(self.urls[data_type], headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching {data_type} data: {response.status_code}")

    def flatten_dict(self, d, parent_key='', sep='_'):
        # Helper function to flatten nested dictionaries and convert lists to strings
        items = []
        for k, v in d.items():
            # If value is a list, convert to a string
            if isinstance(v, list):
                v = ', '.join(map(str, v))  # Convert list to a string (comma-separated)

            # Remove 'contributor' prefix if present
            if k.startswith('contributor'):
                k = k[len('contributor_'):] 

            # Generate key name
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):  # If value is a dictionary, recursively call
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v)) 

        return dict(items)

    def save_to_db(self, data, data_type):
        # Function to create database and insert fetched data
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        for record in data.get('data', []):
            # Flatten nested fields
            flattened_record = self.flatten_dict(record)

            # Determine date field
            if data_type in ["enhanced_tag", "restmode_period"]:
                date_field = flattened_record.get("start_day")
            elif data_type in ["ring_configuration"]:
                date_field = flattened_record.get("set_up_at")
            else:
                date_field = flattened_record.get("day")

            if data_type not in ["ring_configuration"] and not date_field:
                print(f"No valid date in record for {data_type}: {record}")
                continue

            # Create table
            keys = list(flattened_record.keys())
            columns = [f"{key} TEXT" for key in keys]
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {data_type} (
                    {"date TEXT PRIMARY KEY," if date_field else ""}
                    {", ".join(columns)}
                )
            """
            cursor.execute(create_table_query)

            # Add missing columns
            cursor.execute(f"PRAGMA table_info({data_type})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for key in keys:
                if key not in existing_columns:
                    cursor.execute(f"ALTER TABLE {data_type} ADD COLUMN {key} TEXT")

            # Insert or update data
            if date_field:
                flattened_record["date"] = date_field

            columns_placeholders = ", ".join(flattened_record.keys())
            placeholders = ", ".join([f":{key}" for key in flattened_record.keys()])
            insert_query = f"""
                INSERT INTO {data_type} ({"date, " if date_field else ""}{columns_placeholders})
                VALUES ({":date, " if date_field else ""}{placeholders})
                {f"ON CONFLICT(date) DO UPDATE SET {', '.join([f'{key} = excluded.{key}' for key in flattened_record.keys() if key != 'date'])}" if date_field else ""}
            """
            cursor.execute(insert_query, flattened_record)

        conn.commit()
        conn.close()

    def run(self):
        for data_type in self.urls.keys():
            try:
                data = self.fetch_data(data_type)
                self.save_to_db(data, data_type)
                print(f"{data_type} data successfully saved.")
            except Exception as e:
                print(f"Error with {data_type}: {e}")

if __name__ == "__main__":
    handler = OuraDataHandler('config.ini')
    handler.run()
