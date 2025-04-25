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

# Initialize Flask app with custom templates directory
app = Flask(__name__, template_folder='ficore_templates')

# Load environment variables
load_dotenv()

# Constants for Google Sheets (same as in the notebook)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:L'
RESULTS_SHEET_NAME = 'FicoreAIResults'
RESULTS_HEADER = ['Email', 'FicoreAIScore', 'FicoreAIRank']
FEEDBACK_FORM_URL = 'https://forms.gle/ficoreai-feedback'
WAITLIST_FORM_URL = 'https://forms.gle/ficoreai-premium-waitlist'
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email'
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
        print("Sheet1 headers set to predetermined values.")
    except Exception as e:
        print(f"Error setting headers: {e}")
        raise

# Append data to Google Sheet
def append_to_sheet(data):
    try:
        set_sheet_headers()
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        body = {'values': [data]}
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    except Exception as e:
        print(f"Error appending to sheet: {e}")
        raise

# Fetch data from Google Sheet
def fetch_data_from_sheet():
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

# Calculate Financial Health Score
def calculate_health_score(df):
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

# Send Email
def send_email(recipient_email, user_name, health_score, score_description, rank, total_users):
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    if not sender_email or not sender_password:
        raise Exception("SENDER_EMAIL or SENDER_PASSWORD environment variable not set.")

    subject = "Your Ficore AI Financial Health Score"
    body = f"""
Dear {user_name},

We have calculated your Ficore AI Financial Health Score based on your recent submission.

- **Score**: {health_score}/100
- **Advice**: {score_description}
- **Rank**: #{int(rank)} out of {total_users} users

Please provide feedback on your experience: {FEEDBACK_FORM_URL}
Join the waitlist for Ficore AI Premium: {WAITLIST_FORM_URL}

Best regards,
The Ficore AI Team
"""
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for attempt in range(3):
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
                print(f"Email successfully sent to {recipient_email} (primary email)")
                return True
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    print(f"Failed to send email to {recipient_email} (primary email) after 3 attempts")
    return False

# Homepage route
@app.route('/')
def home():
    return render_template('index.html')

# Form submission route
@app.route('/submit', methods=['POST'])
def submit():
    # Extract form data
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    business_name = request.form.get('business_name')
    income_revenue = float(request.form.get('income_revenue'))
    expenses_costs = float(request.form.get('expenses_costs'))
    debt_loan = float(request.form.get('debt_loan'))
    debt_interest_rate = float(request.form.get('debt_interest_rate'))
    auto_email = 'TRUE'
    phone_number = request.form.get('phone_number')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    user_type = request.form.get('user_type')
    email = request.form.get('email')

    # Prepare data for Google Sheet
    data = [
        timestamp, business_name, income_revenue, expenses_costs, debt_loan,
        debt_interest_rate, auto_email, phone_number, first_name, last_name,
        user_type, email
    ]
    append_to_sheet(data)

    # Fetch updated data
    sheet_data = fetch_data_from_sheet()
    if not sheet_data:
        return "Error: No data found in Google Sheet.", 500

    # Convert to DataFrame
    headers = sheet_data[0]
    rows = sheet_data[1:]
    all_users_df = pd.DataFrame(rows, columns=headers)

    # Convert numeric columns to float
    numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
    for col in numeric_cols:
        all_users_df[col] = pd.to_numeric(all_users_df[col], errors='coerce').fillna(0)

    # Calculate health scores
    all_users_df = calculate_health_score(all_users_df)

    # Sort by HealthScore and assign ranks
    all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
    all_users_df['Rank'] = range(1, len(all_users_df) + 1)

    # Filter for the current user
    user_df = all_users_df[all_users_df['Email'] == email]
    if user_df.empty:
        return f"Error: No data found for user with email: {email}", 500

    # Extract user data
    user_row = user_df.iloc[0]
    health_score = user_row['HealthScore']
    rank = user_row['Rank']
    total_users = len(all_users_df)
    score_description = user_row['ScoreDescription']

    # Send email
    user_name = f"{first_name} {last_name}"
    send_email(email, user_name, health_score, score_description, rank, total_users)

    # Redirect to dashboard
    return redirect(url_for('dashboard', email=email))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    # Get the user's email from query parameters
    email = request.args.get('email', 'test@example.com')

    # Fetch data from Google Sheets
    sheet_data = fetch_data_from_sheet()
    if not sheet_data:
        return "Error: No data found in Google Sheet.", 500

    # Convert to DataFrame
    headers = sheet_data[0]
    rows = sheet_data[1:]
    all_users_df = pd.DataFrame(rows, columns=headers)

    # Convert numeric columns to float
    numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
    for col in numeric_cols:
        all_users_df[col] = pd.to_numeric(all_users_df[col], errors='coerce').fillna(0)

    # Calculate health scores for all users
    all_users_df = calculate_health_score(all_users_df)

    # Sort by HealthScore and assign ranks
    all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
    all_users_df['Rank'] = range(1, len(all_users_df) + 1)

    # Filter for the current user
    user_df = all_users_df[all_users_df['Email'] == email]
    if user_df.empty:
        return f"Error: No data found for user with email: {email}", 500

    # Extract user data
    user_row = user_df.iloc[0]
    health_score = user_row['HealthScore']
    rank = user_row['Rank']
    total_users = len(all_users_df)
    score_description = user_row['ScoreDescription']
    cash_flow_score = round(user_row['NormCashFlow'] * 100, 2)
    debt_to_income_score = round(user_row['NormDebtToIncome'] * 100, 2)
    debt_interest_score = round(user_row['NormDebtInterest'] * 100, 2)

    # Create Plotly charts
    # Score Breakdown Bar Chart
    breakdown_data = {
        "Component": ["Cash Flow", "Debt-to-Income Ratio", "Debt Interest Burden"],
        "Score": [cash_flow_score, debt_to_income_score, debt_interest_score]
    }
    breakdown_df = pd.DataFrame(breakdown_data)
    fig_breakdown = px.bar(
        breakdown_df,
        x="Score",
        y="Component",
        orientation='h',
        title="Score Breakdown",
        labels={"Score": "Score (out of 100)"},
        color="Component",
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    fig_breakdown.update_layout(showlegend=False)
    breakdown_plot = fig_breakdown.to_html(full_html=False, include_plotlyjs=False)

    # Comparison Line Chart
    fig_comparison = go.Figure()
    fig_comparison.add_trace(
        go.Scatter(
            x=list(range(1, len(all_users_df) + 1)),
            y=all_users_df['HealthScore'],
            mode='lines+markers',
            name='All Users',
            line=dict(color='blue')
        )
    )
    fig_comparison.add_trace(
        go.Scatter(
            x=[int(rank)],
            y=[health_score],
            mode='markers',
            name='Your Score',
            marker=dict(color='red', size=12, symbol='star')
        )
    )
    fig_comparison.update_layout(
        title="How You Compare to Others",
        xaxis_title="User Rank",
        yaxis_title="Health Score",
        showlegend=True
    )
    comparison_plot = fig_comparison.to_html(full_html=False, include_plotlyjs=False)

    # Render the dashboard template
    return render_template(
        'dashboard.html',
        health_score=health_score,
        rank=int(rank),
        total_users=total_users,
        score_description=score_description,
        breakdown_plot=breakdown_plot,
        comparison_plot=comparison_plot
    )

if __name__ == "__main__":
    # For Render, bind to 0.0.0.0 and use the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
