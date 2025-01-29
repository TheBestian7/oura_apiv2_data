# oura_apiv2_data

## Overview
The Oura Data Handler program is a Python application that fetches and stores health-related data from the Oura API v2. It connects to the Oura platform via OAuth2 authentication, retrieves various types of health data over a specified date range, and saves the data to an SQLite database.

## Features
- **OAuth2 Authentication**: The program handles OAuth2 authentication with Oura to securely access data.
- **Data Fetching**: It fetches a variety of health data such as daily activity, cardiovascular age, readiness, sleep, and more.
- **Data Storage**: The fetched data is stored in an SQLite database, with each data type having its own table. The data is flattened to make it easier to store and query.
- **Token Management**: It automatically handles token expiration and refresh, ensuring that the program can always access the necessary data.

## Configuration
Rename config.ini sample -> config.ini
Create or use an existing Callback URL and fill in the config.ini
Visit >>> https://cloud.ouraring.com/oauth/applications <<<
LogIn with your Oura Credentials and create a new Application.
Fill in the Callback URL in the Application Field >>>Redirect URIs<<<
Fill in your client_id and client_secret in config.ini
Change Name for db_file and token_file if wanted and change the start_date.
Leave end_date empty for today or fill in if needed.
