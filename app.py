from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app with custom templates directory
app = Flask(__name__, template_folder='ficore_templates')

# Load environment variables
load_dotenv()

# Constants for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:M'  # Updated range to include new Badges column
RESULTS_SHEET_NAME = 'FicoreAIResults'
RESULTS_HEADER = ['Email', 'FicoreAIScore', 'FicoreAIRank']
FEEDBACK_FORM_URL = 'https://forms.gle/NkiLicSykLyMnhJk7'
WAITLIST_FORM_URL = 'https://forms.gle/3kXnJuDatTm8bT3x7'
CONSULTANCY_FORM_URL = 'https://forms.gle/rfHhpD71MjLpET2K9'
# Course URLs updated to YouTube channel videos
INVESTING_COURSE_URL = 'https://youtube.com/watch?v=investing-2025-video-id'
SAVINGS_COURSE_URL = 'https://youtube.com/watch?v=savings-2025-video-id'
DEBT_COURSE_URL = 'https://youtube.com/watch?v=debt-management-2025-video-id'
RECOVERY_COURSE_URL = 'https://youtube.com/watch?v=financial-recovery-2025-video-id'
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email', 'Badges'
]

# Authenticate with Google Sheets
def authenticate_google_sheets():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON environment variable not set.")
    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return build('sheets', 'v4', credentials=creds)
    except json.JSONDecodeError as e:
        raise Exception(f"Error decoding GOOGLE_CREDENTIALS_JSON: {e}")
    except Exception as e:
        raise Exception(f"Error authenticating with Google Sheets: {e}")

# Set Google Sheet headers
def set_sheet_headers():
    try:
        service = authenticate_google_sheets()
        if not service:
            raise Exception("Google Sheets authentication failed.")
        sheet = service.spreadsheets()
        body = {'values': [PREDETERMINED_HEADERS]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info("Sheet1 headers set to predetermined values.")
    except Exception as e:
        logger.error(f"Error setting headers: {e}")
        raise

# Get the number of rows in the sheet to determine where to append
def get_row_count():
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        return len(values) if values else 0
    except Exception as e:
        logger.error(f"Error getting row count: {e}")
        raise

# Append data to Google Sheet using update to ensure all columns are set
def append_to_sheet(data):
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()

        # Set headers if the sheet is empty
        row_count = get_row_count()
        if row_count == 0:
            set_sheet_headers()
            row_count = 1  # After setting headers

        # Append the data by updating the next row
        range_to_update = f'Sheet1!A{row_count + 1}:M{row_count + 1}'
        body = {'values': [data]}  # data already has 13 elements
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info(f"Data appended to sheet at row {row_count + 1}.")
        time.sleep(1)  # Small delay to allow propagation
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        raise

# Fetch data from Google Sheet with retry mechanism
def fetch_data_from_sheet(max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            service = authenticate_google_sheets()
            if not service:
                raise Exception("Google Sheets authentication failed.")
            sheet = service.spreadsheets()
            result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
            values = result.get('values', [])
            
            if not values:
                logger.info(f"Attempt {attempt + 1}: No data found in Google Sheet.")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    continue
                return None
            
            headers = values[0]
            rows = values[1:] if len(values) > 1 else []
            expected_columns = PREDETERMINED_HEADERS
            
            # Log the fetched data
            logger.debug(f"Attempt {attempt + 1}: Fetched headers: {headers}")
            logger.debug(f"Attempt {attempt + 1}: Fetched rows: {rows}")

            # If headers don't match expected columns, reset the headers
            if headers != expected_columns:
                logger.warning(f"Attempt {attempt + 1}: Headers do not match expected columns. Resetting headers.")
                set_sheet_headers()
                if not rows:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    return None
                # Normalize rows to match expected columns
                normalized_rows = []
                for row in rows:
                    if len(row) < len(expected_columns):
                        row = row + [""] * (len(expected_columns) - len(row))
                    elif len(row) > len(expected_columns):
                        row = row[:len(expected_columns)]
                    normalized_rows.append(row)
                rows = normalized_rows
            else:
                # Ensure rows match the number of headers
                normalized_rows = []
                for row in rows:
                    if len(row) < len(headers):
                        row = row + [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                    normalized_rows.append(row)
                rows = normalized_rows
            
            # Create DataFrame with correct column names
            if not rows:
                logger.info(f"Attempt {attempt + 1}: No data rows found, creating empty DataFrame.")
                df = pd.DataFrame(columns=expected_columns)
            else:
                df = pd.DataFrame(rows, columns=headers)
                # Ensure all expected columns are present
                for col in expected_columns:
                    if col not in df.columns:
                        df[col] = ""
                # Reorder columns to match expected_columns
                df = df[expected_columns]
            
            logger.debug(f"Attempt {attempt + 1}: Created DataFrame with shape {df.shape}")
            logger.debug(f"Attempt {attempt + 1}: DataFrame head:\n{df.head()}")
            return df
        
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: Error fetching data from Google Sheet: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            raise
    raise Exception("Max retries reached while fetching data from Google Sheet.")

# Calculate Financial Health Score, determine course suggestion, and assign badges
def calculate_health_score(df):
    try:
        if df.empty:
            logger.warning("Empty DataFrame passed to calculate_health_score.")
            return df
        
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

        def score_description_and_course(row):
            score = row['HealthScore']
            cash_flow = row['CashFlowRatio']
            debt_to_income = row['DebtToIncomeRatio']
            debt_interest = row['DebtInterestBurden']
            
            if score >= 75:
                return ('Stable; invest excess now',
                        'Ficore Simplified Investing Course: How to Invest in 2025 for Better Gains',
                        INVESTING_COURSE_URL)
            elif score >= 50:
                if cash_flow < 0.3 or debt_interest > 0.5:
                    return ('At Risk; manage expense',
                            'Ficore Debt and Expense Management: Regain Control in 2025',
                            DEBT_COURSE_URL)
                return ('Moderate; save monthly',
                        'Ficore Savings Mastery: Building a Financial Safety Net in 2025',
                        SAVINGS_COURSE_URL)
            elif score >= 25:
                if debt_to_income > 0.5 or debt_interest > 0.5:
                    return ('At Risk; pay off debt, manage expense',
                            'Ficore Debt and Expense Management: Regain Control in 2025',
                            DEBT_COURSE_URL)
                return ('At Risk; manage expense',
                        'Ficore Debt and Expense Management: Regain Control in 2025',
                        DEBT_COURSE_URL)
            else:
                if debt_to_income > 0.5 or cash_flow < 0.3:
                    return ('Critical; add source of income, pay off debt, manage expense',
                            'Ficore Financial Recovery: First Steps to Stability in 2025',
                            RECOVERY_COURSE_URL)
                return ('Critical; seek financial help',
                        'Ficore Financial Recovery: First Steps to Stability in 2025',
                        RECOVERY_COURSE_URL)

        df[['ScoreDescription', 'CourseTitle', 'CourseURL']] = df.apply(
            score_description_and_course, axis=1, result_type='expand')
        return df
    except Exception as e:
        logger.error(f"Error calculating health score: {e}")
        raise

# Assign badges based on user submission
def assign_badges(user_df, all_users_df):
    badges = []
    user_row = user_df.iloc[0]
    email = user_row['Email']
    health_score = user_row['HealthScore']
    current_debt = user_row['DebtLoan']

    # Check for "First Health Score Completed!" badge
    user_submissions = all_users_df[all_users_df['Email'] == email]
    if len(user_submissions) == 1:  # This is the user's first submission
        badges.append("First Health Score Completed!")

    # Check for "Financial Stability Achieved!" badge
    if health_score > 80:
        badges.append("Financial Stability Achieved!")

    # Check for "Debt Slayer!" badge
    if len(user_submissions) > 1:  # User has previous submissions
        previous_submission = user_submissions.iloc[-2]  # Second-to-last submission
        previous_debt = float(previous_submission['DebtLoan'])
        if current_debt < previous_debt:
            badges.append("Debt Slayer!")

    logger.debug(f"Assigned badges for email {email}: {badges}")
    return badges

# Update badges in Google Sheet
def update_badges_in_sheet(email, new_badges):
    try:
        logger.debug(f"Starting badge update for email: {email} with new badges: {new_badges}")
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            logger.info("No data found in Google Sheet for badge update.")
            return

        headers = values[0]
        rows = values[1:]
        logger.debug(f"Fetched headers for badge update: {headers}")
        logger.debug(f"F
