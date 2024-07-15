import os
import sys
import requests
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables
VAPI_URL = os.getenv('VAPI_URL')
PEPFACTOR_OUT_ASSISTANT_ID = os.getenv('ASSISTANT_ID')
PEPFACTOR_IN_ASSISTANT_ID = os.getenv('INBOUND_ASSISTANT_ID')
GREYCORP_OUT_ASSISTANT_ID = os.getenv('GREYCORP_OUT_ASSISTANT_ID')
GREYCORP_IN_ASSISTANT_ID = os.getenv('GREYCORP_IN_ASSISTANT_ID')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

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
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        all_calls.extend(data)
        
        if len(data) < params["limit"]:
            break
        
        params["createdAtLt"] = data[-1]["createdAt"]
    
    print(f"Total calls fetched: {len(all_calls)}")
    return all_calls

# Function to calculate the duration of a call
def calculate_duration(start_time, end_time):
    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    duration = (end - start).total_seconds()
    return duration

# Function to filter calls that last longer than a specified duration
def filter_calls(calls, min_duration=20):
    filtered_calls = []
    for call in calls:
        if 'startedAt' in call and 'endedAt' in call:
            try:
                duration = calculate_duration(call['startedAt'], call['endedAt'])
                if duration > min_duration:
                    phone_number = call.get('customer', {}).get('number', 'N/A')
                    analysis = call.get('analysis', {})
                    filtered_calls.append([
                        call['id'],
                        phone_number,
                        duration,
                        call['startedAt'],
                        call['endedAt'],
                        analysis.get('summary', 'N/A'),
                        analysis.get('successEvaluation', 'N/A'),
                        call['transcript']
                    ])
            except ValueError as e:
                print(f"Error calculating duration for call {call['id']}: {str(e)}")
    return filtered_calls

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

def update_pepfactor_outbound():
    out_calls = fetch_call_logs(VAPI_URL, PEPFACTOR_OUT_ASSISTANT_ID, BEARER_TOKEN)
    filtered_out_calls = filter_calls(out_calls)
    RANGE_NAME_OUT = 'Sheet1!A1:H'
    outbound_values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_out_calls
    outbound_result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME_OUT, outbound_values)
    print(f"{outbound_result.get('updatedCells')} outbound cells updated.")

def update_pepfactor_inbound():
    in_calls = fetch_call_logs(VAPI_URL, PEPFACTOR_IN_ASSISTANT_ID, BEARER_TOKEN)
    filtered_in_calls = filter_calls(in_calls)
    RANGE_NAME_IN = 'Sheet2!A1:H'
    inbound_values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_in_calls
    inbound_result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME_IN, inbound_values)
    print(f"{inbound_result.get('updatedCells')} inbound cells updated.")

def update_greycorp_outbound():
    calls = fetch_call_logs(VAPI_URL, GREYCORP_OUT_ASSISTANT_ID, BEARER_TOKEN)
    filtered_calls = filter_calls(calls)
    RANGE_NAME = 'Sheet3!A1:H'
    values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_calls
    result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, values)
    print(f"{result.get('updatedCells')} cells updated for GreyCorp outbound calls.")

def update_greycorp_inbound():
    calls = fetch_call_logs(VAPI_URL, GREYCORP_IN_ASSISTANT_ID, BEARER_TOKEN)
    filtered_calls = filter_calls(calls)
    RANGE_NAME = 'Sheet4!A1:H'
    values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_calls
    result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, values)
    print(f"{result.get('updatedCells')} cells updated for GreyCorp inbound calls.")

# Main function to fetch call logs, filter them, and update the Google Sheet
def main(sheet_name=None):
    if sheet_name is None:
        # Update all sheets
        update_pepfactor_outbound()
        update_pepfactor_inbound()
        update_greycorp_outbound()
        update_greycorp_inbound()
    elif sheet_name == "pepfactor_outbound":
        update_pepfactor_outbound()
    elif sheet_name == "pepfactor_inbound":
        update_pepfactor_inbound()
    elif sheet_name == "greycorp_outbound":
        update_greycorp_outbound()
    elif sheet_name == "greycorp_inbound":
        update_greycorp_inbound()
    else:
        print("Invalid sheet name")
        return

if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Usage: python main.py <SheetName>")
        sys.exit(1)

    sheet_name = sys.argv[1] if len(sys.argv) == 2 else None
    main(sheet_name)
