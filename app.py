from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd
import smtplib
import numpy as np
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Load environment variables at the start
load_dotenv()

# Flask setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'ficore_templates')

app = Flask(__name__, template_folder=TEMPLATES_FOLDER)

# Constants for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:K'
RESULTS_SHEET_NAME = 'FicoreAIResults'
RESULTS_HEADER = ['Email', 'FicoreAIScore', 'FicoreAIRank']
FEEDBACK_FORM_URL = 'https://forms.gle/ficoreai-feedback'

# --- Helper Functions ---

def authenticate_google_sheets():
    """Authenticate with Google Sheets API using OAuth credentials."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def fetch_data_from_sheet():
    """Fetch data from Sheet1 in the Google Sheet."""
    try:
        creds = authenticate_google_sheets()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            return None
        return values
    except Exception as e:
        raise Exception(f"Failed to fetch data from Google Sheet: {str(e)}")

def send_email(to_email, first_name, last_name, rank, timestamp, health_score, score_description, server):
    """Send an email with the Financial Health Score and advice to the user."""
    max_retries = 3
    retry_delay = 5
    full_name = f"{first_name} {last_name}".strip()
    for attempt in range(max_retries):
        try:
            msg = MIMEMultipart()
            msg['From'] = server.user
            msg['To'] = to_email
            msg['Subject'] = f"Ficore AI: Your Financial Health Score, {full_name}"
            html = (
                '<html>\n'
                '    <body style="font-family: Arial, sans-serif; color: #333;">\n'
                '        <div style="text-align: center;">\n'
                '            <img src="https://www.freepik.com/free-photos-vectors/personal-finance-logo" alt="Ficore AI Logo" style="width: 150px; margin-bottom: 20px;" />\n'
                '        </div>\n'
                '        <h2 style="color: #2c3e50; text-align: center;">Ficore AI Financial Health Score</h2>\n'
                f'        <p>Hi {first_name},</p>\n'
                '        <p>Here’s your Ficore AI Financial Health Score and advice to improve your financial health, based on your recent submission.</p>\n'
                '        <table style="border-collapse: collapse; width: 100%; max-width: 600px; margin: 20px 0;">\n'
                '            <tr style="background-color: #2c3e50; color: white;">\n'
                '                <th style="border: 1px solid #ddd; padding: 8px;">Rank</th>\n'
                '                <th style="border: 1px solid #ddd; padding: 8px;">Timestamp</th>\n'
                '                <th style="border: 1px solid #ddd; padding: 8px;">Name</th>\n'
                '                <th style="border: 1px solid #ddd; padding: 8px;">Health Score</th>\n'
                '                <th style="border: 1px solid #ddd; padding: 8px;">Advice</th>\n'
                '            </tr>\n'
                '            <tr>\n'
                f'                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{rank}</td>\n'
                f'                <td style="border: 1px solid #ddd; padding: 8px;">{timestamp}</td>\n'
                f'                <td style="border: 1px solid #ddd; padding: 8px;">{full_name}</td>\n'
                f'                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{health_score}</td>\n'
                f'                <td style="border: 1px solid #ddd; padding: 8px;">{score_description}</td>\n'
                '            </tr>\n'
                '        </table>\n'
                f'        <p>{first_name}, take one step today to grow stronger financially — for your business, your goals, your future. We want you to grow, and the time is Now!</p>\n'
                '        <div style="text-align: center; margin: 20px 0;">\n'
                '            <a href="https://forms.gle/ficoreai-feedback" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-right: 10px;">Help us improve! Share your feedback (takes 1 min)</a>\n'
                '            <a href="https://calendly.com/ficoreai" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Book Consultation</a>\n'
                '        </div>\n'
                '        <p>Best regards,<br>Hassan<br>Ficore AI - Empowering African Financial Growth<br>Email: {server.user} | Website: ficore.com.ng (coming soon)</p>\n'
                '    </body>\n'
                '</html>'
            )
            msg.attach(MIMEText(html, 'html'))
            server.send_message(msg)
            time.sleep(1)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise Exception(f"Failed to send email to {to_email} for {full_name} after {max_retries} attempts: {str(e)}")

def calculate_health_score(df):
    """Calculate the Financial Health Score based on income, expenses, debt, and interest rate."""
    try:
        df['HealthScore'] = 0.0
        df['IncomeRevenueSafe'] = df['IncomeRevenue'].replace(0, 1e-10)
        df['CashFlowRatio'] = (df['IncomeRevenue'] - df['ExpensesCosts']) / df['IncomeRevenueSafe']
        df['DebtToIncomeRatio'] = df['DebtLoan'] / df['IncomeRevenueSafe']
        df['DebtInterestBurden'] = df['DebtInterestRate'].clip(lower=0) / 20
        df['DebtInterestBurden'] = df['DebtInterestBurden'].clip(upper=1)
        df['NormCashFlow'] = df['CashFlowRatio'].clip(0, 1)
        df['NormDebtToIncome'] = 1 - df['DebtToIncomeRatio'].clip(0, 1)
        df['NormDebtInterest'] = 1 - df['DebtInterestBurden']
        df['HealthScore'] = (df['NormCashFlow'] * 0.333 +
                            df['NormDebtToIncome'] * 0.333 +
                            df['NormDebtInterest'] * 0.333) * 100
        df['HealthScore'] = df['HealthScore'].round(2)

        def score_description(row):
            score = row['HealthScore']
            cash_flow = row['CashFlowRatio']
            debt_to_income = row['DebtToIncomeRatio']
            debt_interest = row['DebtInterestBurden']
            if score >= 75:
                return 'Stable; invest excess now'
            elif score >= 50:
                if cash_flow < 0.3 or debt_interest > 0.5:
                    return 'At Risk; manage expense'
                return 'Moderate; save monthly'
            elif score >= 25:
                if debt_to_income > 0.5 or debt_interest > 0.5:
                    return 'At Risk; pay off debt, manage expense'
                return 'At Risk; manage expense'
            else:
                if debt_to_income > 0.5 or cash_flow < 0.3:
                    return 'Critical; add source of income, pay off debt, manage expense'
                return 'Critical; seek financial help'

        df['ScoreDescription'] = df.apply(score_description, axis=1)
        return df
    except Exception as e:
        raise Exception(f"Failed to calculate HealthScore: {str(e)}")

def create_results_sheet():
    """Create the FicoreAIResults sheet if it doesn't exist and set up headers."""
    try:
        creds = authenticate_google_sheets()
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet = service.spreadsheets()
        sheets = spreadsheet.get(spreadsheetId=SPREADSHEET_ID).execute().get('sheets', [])
        sheet_names = [sheet['properties']['title'] for sheet in sheets]
        if RESULTS_SHEET_NAME not in sheet_names:
            body = {'properties': {'title': RESULTS_SHEET_NAME}}
            spreadsheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': [{'addSheet': body}]}).execute()
            header_range = f'{RESULTS_SHEET_NAME}!A1:C1'
            body = {'values': [RESULTS_HEADER]}
            spreadsheet.values().update(spreadsheetId=SPREADSHEET_ID, range=header_range, valueInputOption='USER_ENTERED', body=body).execute()
    except Exception as e:
        raise Exception(f"Failed to create or set up results sheet: {str(e)}")

def write_results_to_sheet(df):
    """Write Health Scores and Ranks to the FicoreAIResults sheet."""
    try:
        creds = authenticate_google_sheets()
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet = service.spreadsheets()
        clear_range = f'{RESULTS_SHEET_NAME}!A2:C'
        spreadsheet.values().clear(spreadsheetId=SPREADSHEET_ID, range=clear_range).execute()
        results_data = []
        for index, row in df[['Email', 'HealthScore', 'Rank']].iterrows():
            results_data.append([row['Email'], float(row['HealthScore']), int(row['Rank'])])
        if results_data:
            body = {'values': results_data}
            range_name = f'{RESULTS_SHEET_NAME}!A2'
            spreadsheet.values().update(spreadsheetId=SPREADSHEET_ID, range=range_name,
                                        valueInputOption='USER_ENTERED', body=body).execute()
    except Exception as e:
        raise Exception(f"Failed to write results to Google Sheet ({RESULTS_SHEET_NAME}): {str(e)}")

def append_to_sheet(data):
    """Append form submission data to Sheet1 and apply formatting."""
    try:
        creds = authenticate_google_sheets()
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet = service.spreadsheets()
        range_name = 'Sheet1!A:K'
        # Append the data
        body = {'values': [data]}
        result = spreadsheet.values().append(spreadsheetId=SPREADSHEET_ID, range=range_name,
                                            valueInputOption='USER_ENTERED', body=body).execute()

        # Get the row number of the newly added row
        sheet_metadata = spreadsheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet = sheet_metadata['sheets'][0]  # Sheet1 is the first sheet
        row_count = sheet['properties']['gridProperties']['rowCount']
        new_row_index = row_count - 1  # The new row is the last row

        # Formatting requests
        requests = [
            # Set column widths
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "dimension": "COLUMNS",
                        "startIndex": 0,  # Column A
                        "endIndex": 1
                    },
                    "properties": {"pixelSize": 150},  # Adjust width for Timestamp
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "dimension": "COLUMNS",
                        "startIndex": 1,  # Column B
                        "endIndex": 2
                    },
                    "properties": {"pixelSize": 120},  # Adjust width for Business Name
                    "fields": "pixelSize"
                }
            },
            # Apply currency formatting to IncomeRevenue, ExpensesCosts, DebtsLoans
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "startRowIndex": new_row_index,
                        "endRowIndex": new_row_index + 1,
                        "startColumnIndex": 2,  # Column C (IncomeRevenue)
                        "endColumnIndex": 5     # Column F (DebtsLoans)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "CURRENCY",
                                "pattern": "$#,##0.00"
                            },
                            "horizontalAlignment": "RIGHT"
                        }
                    },
                    "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"
                }
            },
            # Apply number formatting to DebtInterestRate
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "startRowIndex": new_row_index,
                        "endRowIndex": new_row_index + 1,
                        "startColumnIndex": 5,  # Column F (DebtInterestRate)
                        "endColumnIndex": 6
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "NUMBER",
                                "pattern": "0.00"
                            },
                            "horizontalAlignment": "RIGHT"
                        }
                    },
                    "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"
                }
            },
            # Ensure text alignment for other columns (left-aligned)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "startRowIndex": new_row_index,
                        "endRowIndex": new_row_index + 1,
                        "startColumnIndex": 0,  # Column A (Timestamp)
                        "endColumnIndex": 2,    # Column B (Business Name)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment)"
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "startRowIndex": new_row_index,
                        "endRowIndex": new_row_index + 1,
                        "startColumnIndex": 6,  # Column G (AutoEmail)
                        "endColumnIndex": 11    # Column K (EntityType)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment)"
                }
            }
        ]

        # Execute the formatting requests
        body = {"requests": requests}
        spreadsheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
    except Exception as e:
        raise Exception(f"Failed to append data to Google Sheet or apply formatting: {str(e)}")

def process_financial_data():
    """Process financial data: calculate Health Scores, rank users, send emails, and update results sheet."""
    try:
        create_results_sheet()
        values = fetch_data_from_sheet()
        if not values:
            raise Exception("No data found in Sheet1 to process.")
        headers = values[0]
        data = values[1:]
        max_cols = len(headers)
        data = [row + [''] * (max_cols - len(row)) for row in data]
        df = pd.DataFrame(data, columns=headers)

        # Validate required columns
        required_columns = ['Timestamp', 'Business Name', 'IncomeRevenue', 'ExpensesCosts', 'DebtsLoans', 'DebtInterestRate', 'AutoEmail', 'EmailTyped', 'First Name', 'Last Name', 'Are you an Individual or SME?']
        if 'First Name' not in df.columns:
            df['First Name'] = ''
        if 'Last Name' not in df.columns:
            df['Last Name'] = ''
        if 'Are you an Individual or SME?' not in df.columns:
            df['Are you an Individual or SME?'] = 'Unknown'
        if 'Business Name' not in df.columns:
            df['Business Name'] = df['First Name'] + ' ' + df['Last Name']
        df['Name'] = df['First Name'] + ' ' + df['Last Name']
        df['Name'] = df['Name'].str.strip()
        df['Name'] = df['Name'].replace('', 'Unknown User')
        if not all(col in df.columns for col in required_columns):
            missing = set(required_columns) - set(df.columns)
            raise Exception(f"Missing required columns in Sheet1: {', '.join(missing)}")

        # Clean and transform data
        df = df.rename(columns={
            'DebtsLoans': 'DebtLoan',
            'EmailTyped': 'Email',
            'Are you an Individual or SME?': 'EntityType'
        })
        df['ID'] = range(1, len(df) + 1)
        numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0)
        df['Email'] = df['Email'].replace('', np.nan)
        df['Email'] = df['Email'].fillna(df['AutoEmail'])
        df['Email'] = df['Email'].fillna('')
        df.to_csv('financials_df.csv', index=False)

        # Calculate Health Scores and rank
        df = calculate_health_score(df)
        df_sorted = df.sort_values('HealthScore', ascending=False)
        df_sorted['Rank'] = range(1, len(df_sorted) + 1)
        df.to_csv('financials_with_healthscore.csv', index=False)

        # Send emails
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        if not sender_email or not sender_password:
            raise Exception("Missing SENDER_EMAIL or SENDER_PASSWORD in .env file. Please add them to your .env file and restart the app.")
        emails_sent = 0
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        try:
            server.login(sender_email, sender_password)
            for index, row in df_sorted.iterrows():
                email = row['Email']
                if pd.isna(email) or (isinstance(email, str) and email.strip() == ''):
                    continue
                send_email(
                    to_email=email,
                    first_name=row['First Name'],
                    last_name=row['Last Name'],
                    rank=row['Rank'],
                    timestamp=row['Timestamp'],
                    health_score=row['HealthScore'],
                    score_description=row['ScoreDescription'],
                    server=server
                )
                emails_sent += 1
        finally:
            server.quit()

        # Write results to sheet
        write_results_to_sheet(df_sorted[['Email', 'HealthScore', 'Rank']].copy())
    except Exception as e:
        raise Exception(f"Pipeline error: {str(e)}")

# --- Flask Routes ---

@app.route('/')
def index():
    """Render the main form page."""
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    """Handle form submission: append data to Sheet1, process financial data, and show success/error page."""
    try:
        data = request.form.to_dict()
        
        # Validate required form fields
        required_fields = ['business_name', 'income_revenue', 'expenses_costs', 'debts_loans', 
                         'debt_interest_rate', 'email_typed', 'first_name', 'last_name', 'entity_type']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise Exception(f"Please fill in all required fields: {', '.join(missing_fields)}")

        # Validate email format
        email = data['email_typed']
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise Exception("Please enter a valid email address.")

        # Validate numeric fields
        numeric_fields = ['income_revenue', 'expenses_costs', 'debts_loans', 'debt_interest_rate']
        for field in numeric_fields:
            try:
                float(data[field])
            except ValueError:
                raise Exception(f"Please enter a valid number for {field.replace('_', ' ').title()}.")

        # Prepare data for Google Sheet
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        sheet_data = [
            timestamp,
            data['business_name'],
            data['income_revenue'],
            data['expenses_costs'],
            data['debts_loans'],
            data['debt_interest_rate'],
            data.get('auto_email', ''),
            data['email_typed'],
            data['first_name'],
            data['last_name'],
            data['entity_type']
        ]

        # Append to Google Sheet and process data
        append_to_sheet(sheet_data)
        process_financial_data()
        return render_template('success.html', data=data)

    except Exception as e:
        # Categorize and simplify error messages for users
        error_message = str(e)
        if "Missing required columns" in error_message:
            user_message = "There was an issue with the Google Sheet configuration. Please contact support."
        elif "Failed to append data" in error_message:
            user_message = "We couldn’t save your submission due to a Google Sheets error. Please try again later."
        elif "Failed to send email" in error_message:
            user_message = "Your submission was saved, but we couldn’t send the confirmation email. Please check your inbox later."
        elif "Missing SENDER_EMAIL or SENDER_PASSWORD" in error_message:
            user_message = "Server configuration error. Please contact support."
        elif "Please fill in all required fields" in error_message:
            user_message = error_message
        elif "Please enter a valid email address" in error_message:
            user_message = error_message
        elif "Please enter a valid number" in error_message:
            user_message = error_message
        else:
            user_message = "An unexpected error occurred. Please try again or contact support."
        return render_template('error.html', error=user_message)

if __name__ == '__main__':
    app.run(debug=True, port=5001)