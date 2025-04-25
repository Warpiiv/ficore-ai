from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd
import smtplib
import time
import re
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
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
DATA_RANGE_NAME = 'Sheet1!A1:L'
RESULTS_SHEET_NAME = 'FicoreAIResults'
RESULTS_HEADER = ['Email', 'FicoreAIScore', 'FicoreAIRank']
FEEDBACK_FORM_URL = 'https://forms.gle/ficoreai-feedback'

# Predetermined headers for Sheet1 (in Google Form order, including AutoEmail)
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email'
]

# --- Helper Functions ---

def authenticate_google_sheets():
    """Authenticate with Google Sheets API using Service Account credentials from environment variable."""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON environment variable not set on Render.")
    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return build('sheets', 'v4', credentials=creds)
    except json.JSONDecodeError as e:
        raise Exception(f"Error decoding GOOGLE_CREDENTIALS_JSON: {e}")
    except Exception as e:
        raise Exception(f"Error authenticating with Google Sheets: {e}")

def set_sheet_headers():
    """Set the headers in Sheet1 to the predetermined headers."""
    try:
        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
        spreadsheet = service.spreadsheets()
        
        # Update the headers in Sheet1
        header_range = 'Sheet1!A1:L1'
        body = {'values': [PREDETERMINED_HEADERS]}
        spreadsheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=header_range,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        print("Sheet1 headers set to predetermined values.")
    except Exception as e:
        raise Exception(f"Failed to set Sheet1 headers: {str(e)}")

def fetch_data_from_sheet():
    """Fetch data from Sheet1 in the Google Sheet."""
    try:
        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            return None
        return values
    except Exception as e:
        raise Exception(f"Failed to fetch data from Google Sheet: {str(e)}")

def send_email(primary_email, fallback_email, first_name, last_name, rank, timestamp, health_score, score_description, cash_flow_ratio, debt_to_income_ratio, debt_interest_burden):
    """Send an email with the Financial Health Score, breakdown, and advice to the user, with a fallback email option."""
    max_retries = 3
    retry_delay = 5
    full_name = f"{first_name} {last_name}".strip()

    # Format the breakdown metrics as percentages
    cash_flow_score = round(cash_flow_ratio * 100, 2)
    debt_to_income_score = round((1 - debt_to_income_ratio) * 100, 2)
    debt_interest_score = round((1 - debt_interest_burden) * 100, 2)

    # Determine status for each metric
    def get_status(score):
        if score >= 75:
            return "Excellent"
        elif score >= 50:
            return "Good"
        elif score >= 25:
            return "Needs Attention"
        else:
            return "Critical"

    cash_flow_status = get_status(cash_flow_score)
    debt_to_income_status = get_status(debt_to_income_score)
    debt_interest_status = get_status(debt_interest_score)

    # Email content (same for both attempts)
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    if not sender_email or not sender_password:
        raise Exception("SENDER_EMAIL or SENDER_PASSWORD environment variables not set.")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['Subject'] = f"Ficore AI: Your Financial Health Score, {full_name}"
    html = (
        '<html>\n'
        '    <body style="font-family: Arial, sans-serif; color: #333;">\n'
        '        <div style="text-align: center;">\n'
        '            <img src="https://www.freepik.com/free-photos-vectors/personal-finance-logo" alt="Ficore AI Logo" style="width: 150px; margin-bottom: 20px;" />\n'
        '        </div>\n'
        '        <h2 style="color: #2c3e50; text-align: center;">Ficore AI Financial Health Score</h2>\n'
        f'        <p>Hi {first_name},</p>\n'
        '        <p>We’re excited to share your Ficore AI Financial Health Score! This score reflects your financial strength based on three key factors: your cash flow, debt-to-income ratio, and debt interest burden. Let’s break it down for you.</p>\n'
        '        <h3 style="color: #2c3e50;">Your Financial Health Overview</h3>\n'
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
        '        <h3 style="color: #2c3e50;">How We Calculated Your Score</h3>\n'
        '        <p>Your Financial Health Score is a combination of three factors, each contributing equally to your overall score (out of 100). Here’s how you performed in each area:</p>\n'
        '        <ul>\n'
        f'            <li><strong>Cash Flow ({cash_flow_score}% - {cash_flow_status}):</strong> This measures how much money you have left after expenses. A higher percentage means you’re managing your expenses well relative to your income.</li>\n'
        f'            <li><strong>Debt-to-Income Ratio ({debt_to_income_score}% - {debt_to_income_status}):</strong> This shows how much of your income goes toward debt. A higher percentage indicates you have less debt relative to your income, which is a good sign.</li>\n'
        f'            <li><strong>Debt Interest Burden ({debt_interest_score}% - {debt_interest_status}):</strong> This reflects the impact of interest rates on your debt. A higher percentage means your debt interest rates are manageable.</li>\n'
        '        </ul>\n'
        f'        <p>{first_name}, your score of {health_score} is a great starting point! Follow the advice above to improve your financial health. We’re here to support you every step of the way—take one small action today to grow stronger financially for your business, your goals, and your future.</p>\n'
        '        <div style="text-align: center; margin: 20px 0;">\n'
        '            <a href="https://forms.gle/ficoreai-feedback" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-right: 10px;">Help us improve! Share your feedback (takes 1 min)</a>\n'
        '            <a href="https://calendly.com/ficoreai" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Book Consultation</a>\n'
        '        </div>\n'
        f'        <p>Best regards,<br>Hassan<br>Ficore AI - Empowering African Financial Growth<br>Email: {sender_email} | Website: ficore.com.ng (coming soon)</p>\n'
        '    </body>\n'
        '</html>'
    )
    msg.attach(MIMEText(html, 'html'))

    # Try sending to the primary email first
    email_addresses = [(primary_email, "primary email"), (fallback_email, "fallback email")]
    email_sent = False

    for email_address, email_type in email_addresses:
        if not email_address:
            continue
        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(sender_email, sender_password)
                msg['To'] = email_address
                server.send_message(msg)
                server.quit()
                time.sleep(1)
                print(f"Email successfully sent to {email_address} ({email_type})")
                email_sent = True
                break  # Exit retry loop on success
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed for {email_address} ({email_type}): {str(e)}. Retrying...")
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to send email to {email_address} ({email_type}) after {max_retries} attempts: {str(e)}")
        if email_sent:
            break  # Exit email address loop if email was sent successfully

    if not email_sent:
        raise Exception(f"Failed to send email to both {primary_email} (primary) and {fallback_email} (fallback) after all attempts.")

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
        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
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
        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
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
        # Ensure the headers are set to the predetermined values before appending data
        set_sheet_headers()

        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
        spreadsheet = service.spreadsheets()
        range_name = 'Sheet1!A:L'
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
            # Apply currency formatting to IncomeRevenue, ExpensesCosts, DebtLoan
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet['properties']['sheetId'],
                        "startRowIndex": new_row_index,
                        "endRowIndex": new_row_index + 1,
                        "startColumnIndex": 2,  # Column C (IncomeRevenue)
                        "endColumnIndex": 5      # Column F (DebtLoan)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "CURRENCY",
                                "pattern": "₦#,##0.00"  # Use Naira symbol
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
                        "endIndex": 2      # Column B (Business Name)
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
                        "endColumnIndex": 12     # Column L (Email)
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
        # Apply formatting
        spreadsheet.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': requests}).execute()
    except Exception as e:
        raise Exception(f"Failed to append data to Google Sheet: {str(e)}")

# --- Flask Routes ---

@app.route('/')
def index():
    """Render the main form page."""
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    """Handle form submission, calculate score for the new user only, and send email to the new user."""
    try:
        # Get form data
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        business_name = request.form.get('business_name', '').strip()
        income_revenue = float(request.form.get('income_revenue', '0').replace(',', ''))
        expenses_costs = float(request.form.get('expenses_costs', '0').replace(',', ''))
        debt_loan = float(request.form.get('debt_loan', '0').replace(',', ''))
        debt_interest_rate = float(request.form.get('debt_interest_rate', '0').replace(',', ''))
        auto_email = request.form.get('auto_email', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        user_type = request.form.get('user_type', '').strip()
        email = request.form.get('email', '').strip()

        # Validate email (both auto_email and email)
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, email) or not re.match(email_pattern, auto_email):
            return render_template('error.html', error_message="Invalid email address.")

        # Prepare data for Google Sheet
        data = [
            timestamp, business_name, income_revenue, expenses_costs, debt_loan,
            debt_interest_rate, auto_email, phone_number, first_name, last_name, user_type, email
        ]

        # Append data to Sheet1
        append_to_sheet(data)

        # Create a DataFrame for the new user to calculate their health score
        headers = ['Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
                   'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email']
        new_user_df = pd.DataFrame([data], columns=headers)

        # Convert numeric columns to float for the new user
        numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
        for col in numeric_cols:
            new_user_df[col] = pd.to_numeric(new_user_df[col], errors='coerce').fillna(0)

        # Calculate Health Score for the new user
        new_user_df = calculate_health_score(new_user_df)

        # Get the new user's health score and description
        health_score = new_user_df['HealthScore'].iloc[0]
        score_description = new_user_df['ScoreDescription'].iloc[0]
        cash_flow_ratio = new_user_df['NormCashFlow'].iloc[0]  # Already clipped between 0 and 1
        debt_to_income_ratio = new_user_df['DebtToIncomeRatio'].iloc[0]  # Raw ratio for calculation
        debt_interest_burden = new_user_df['DebtInterestBurden'].iloc[0]  # Already clipped between 0 and 1

        # Fetch all data from Sheet1 to determine the rank
        sheet_data = fetch_data_from_sheet()
        if not sheet_data:
            # If no previous data, the new user is rank 1
            rank = 1
            all_users_df = new_user_df
        else:
            # Convert existing data to DataFrame
            headers = sheet_data[0]
            rows = sheet_data[1:]
            all_users_df = pd.DataFrame(rows, columns=headers)

            # Convert numeric columns to float for existing users
            for col in numeric_cols:
                all_users_df[col] = pd.to_numeric(all_users_df[col], errors='coerce').fillna(0)

            # Calculate health scores for existing users (to determine rank)
            all_users_df = calculate_health_score(all_users_df)

            # Append the new user to the DataFrame
            all_users_df = pd.concat([all_users_df, new_user_df], ignore_index=True)

            # Sort by HealthScore (descending) and assign ranks
            all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
            all_users_df['Rank'] = range(1, len(all_users_df) + 1)

            # Get the new user's rank
            rank = all_users_df[all_users_df['Email'] == email]['Rank'].iloc[-1]

        # Create or update the FicoreAIResults sheet with the new rankings
        create_results_sheet()
        write_results_to_sheet(all_users_df)

        # Send email to the new user with fallback option
        send_email(email, auto_email, first_name, last_name, rank, timestamp, health_score, score_description,
                   cash_flow_ratio, debt_to_income_ratio, debt_interest_burden)

        # Render success page
        return render_template('success.html', first_name=first_name, health_score=health_score,
                             rank=rank, score_description=score_description)

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        return render_template('error.html', error_message=error_message)

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
