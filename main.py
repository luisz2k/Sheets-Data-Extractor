import os
import requests
import json
from datetime import datetime
import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables
VAPI_URL = os.getenv('VAPI_URL')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Timezone for Sydney, Australia
SYDNEY_TZ = pytz.timezone('Australia/Sydney')

# Function to fetch call logs from the Vapi API
def fetch_call_logs(url, assistant_id, bearer_token):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    params = {
        "assistantId": assistant_id,
        "limit": 100  # Maximum allowed per request
    }
    all_calls = []
    
    while True:
        # Make a GET request to the API with a limit of 100 calls (the max allowed per request)
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()

        # Add the fetched calls to our list
        all_calls.extend(data)
        
        # Check if we've reached the end of the available data
        if len(data) < params["limit"]:
            break
        
        # Prepare for the next page by updating the createdAtLt parameter
        params["createdAtLt"] = data[-1]["createdAt"]
    
    print(f"Total calls fetched: {len(all_calls)}")
    return all_calls

# Function to calculate the duration of a call
def calculate_duration(start_time, end_time):
    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    duration = (end - start).total_seconds()
    return duration

# Function to format datetime to dd/mm/yyyy hh:mm:ss
def format_datetime(dt_str):
    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    dt_sydney = dt.astimezone(SYDNEY_TZ)
    return dt_sydney.strftime('%d/%m/%Y %I:%M:%S %p')

# Function to extract relevant call information
def extract_call_info(calls):
    call_info = []
    for call in calls:
        if 'startedAt' in call and 'endedAt' in call:
            try:
                duration = calculate_duration(call['startedAt'], call['endedAt'])
                phone_number = call.get('customer', {}).get('number', 'N/A')
                analysis = call.get('analysis', {})
                costBreakdown = call.get('costBreakdown', {})
                analysisCostBreakdown = costBreakdown.get('analysisCostBreakdown', {})
                call_info.append([
                    call['id'],
                    phone_number,
                    duration,
                    format_datetime(call['startedAt']),
                    format_datetime(call['endedAt']),
                    analysis.get('summary', 'N/A'),
                    analysis.get('successEvaluation', 'N/A'),
                    call['transcript'],
                    call['endedReason'],
                    call['recordingUrl'], 
                    costBreakdown.get('total', 'N/A'), # total cost of the call in USD.
                    costBreakdown.get('stt', 'N/A'), # cost of the speech-to-text service
                    costBreakdown.get('llm', 'N/A'), # cost of the language model
                    costBreakdown.get('tts', 'N/A'), # cost of the text-to-speech service
                    costBreakdown.get('vapi', 'N/A'), # cost of Vapi
                    analysisCostBreakdown.get('summary', 'N/A'), # cost to summarize the call 
                    analysisCostBreakdown.get('structuredData', 'N/A'), # cost to extract structured data from the call
                    analysisCostBreakdown.get('successEvaluation', 'N/A'), # cost to evaluate if the call was successful
                ])
            except ValueError as e:
                print(f"Error calculating duration for call {call['id']}: {str(e)}")
    return call_info

# Function to update the Google Sheet with call data
def update_google_sheet(service_account_file, spreadsheet_id, range_name, data):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    result = sheet.values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body={'values': data}).execute()

    return result

# Main function to fetch call logs, extract info, and update the Google Sheet
def main():
    calls = fetch_call_logs(VAPI_URL, ASSISTANT_ID, BEARER_TOKEN)
    call_info = extract_call_info(calls)

    # Google Sheets Export
    RANGE_NAME = 'Sheet1!A1:Z'  # Adjust based on your needs

    # Prepare the data
    values = [['ID', 'Phone Number', 'Duration (s)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript', 'Ended Reason', 'Recording Url', 'Total Cost (USD)', 'STT Cost', 'LLM Cost', 'TTS Cost', 'Vapi Cost', 'Summary Cost', 'Structured Data Cost', 'Success Evaluation Cost']] + call_info

    result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, values)
    print(f"{result.get('updatedCells')} cells updated.")

if __name__ == "__main__":
    main()
