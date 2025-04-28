from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
import os
import pandas as pd
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import logging
from markupsafe import Markup
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='ficore_templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super-secret-key')  # Required for flash messages and CSRF
csrf = CSRFProtect(app)

# Configure caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})  # In-memory cache; use 'redis' for production

# Load environment variables
load_dotenv()

# Constants for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:M'
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email', 'Badges'
]

# Authenticate with Google Sheets
def authenticate_google_sheets():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON environment variable not set.")
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

# Get the number of rows in the sheet
def get_row_count():
    service = authenticate_google_sheets()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
    values = result.get('values', [])
    return len(values) if values else 0

# Append new data to Google Sheet
def append_to_sheet(data):
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        row_count = get_row_count()
        range_to_update = f'Sheet1!A{row_count + 1}:M{row_count + 1}'
        body = {'values': [data]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption='RAW',
            body=body
        ).execute()
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        raise

# Fetch data from Google Sheet with caching
@cache.memoize(timeout=300)  # Cache for 5 minutes
def fetch_data_from_sheet():
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            return pd.DataFrame(columns=PREDETERMINED_HEADERS)
        headers = values[0]
        rows = values[1:]
        df = pd.DataFrame(rows, columns=headers)
        for col in ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise

# Assign badges based on user metrics
def assign_badges(row):
    badges = []
    if row['HealthScore'] >= 75:
        badges.append("Financial Pro")
    if row['HealthScore'] >= 50:
        badges.append("Steady Saver")
    if row['DebtToIncomeRatio'] < 0.2:
        badges.append("Debt Master")
    return ",".join(badges) if badges else ""

# Calculate health scores
def calculate_health_score(df):
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

    # Score description
    df['ScoreDescription'] = df['HealthScore'].apply(
        lambda x: 'Excellent' if x >= 75 else 'Moderate' if x >= 50 else 'At Risk'
    )
    # Personalized course recommendations
    def get_course(row):
        if row['HealthScore'] < 50:
            return "Debt Management Basics", "https://example.com/debt-course"
        elif row['HealthScore'] < 75:
            return "Budget Optimization", "https://example.com/budget-course"
        return "Advanced Financial Planning", "https://example.com/advanced-course"
    df[['CourseTitle', 'CourseURL']] = df.apply(get_course, axis=1, result_type='expand')

    # Assign badges
    df['Badges'] = df.apply(assign_badges, axis=1)
    return df

# Validate email format
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Form submission
@app.route('/submit', methods=['POST'])
@csrf.exempt  # CSRF handled by Flask-WTF in the form
def submit():
    try:
        # Validate required fields
        required_fields = ['business_name', 'income_revenue', 'expenses_costs', 'debt_loan',
                          'debt_interest_rate', 'auto_email', 'email', 'first_name']
        for field in required_fields:
            if not request.form.get(field):
                flash(f"Missing required field: {field.replace('_', ' ').title()}", "error")
                return render_template('index.html'), 400

        # Validate emails
        auto_email = request.form.get('auto_email').strip()
        email = request.form.get('email').strip()
        if not is_valid_email(email) or not is_valid_email(auto_email):
            flash("Invalid email format.", "error")
            return render_template('index.html'), 400
        if auto_email != email:
            flash("Emails do not match.", "error")
            return render_template('index.html'), 400

        # Validate numeric fields
        try:
            income_revenue = float(request.form.get('income_revenue').replace(',', ''))
            expenses_costs = float(request.form.get('expenses_costs').replace(',', ''))
            debt_loan = float(request.form.get('debt_loan').replace(',', ''))
            debt_interest_rate = float(request.form.get('debt_interest_rate').replace(',', ''))
            if any(x < 0 for x in [income_revenue, expenses_costs, debt_loan, debt_interest_rate]):
                flash("Financial values cannot be negative.", "error")
                return render_template('index.html'), 400
        except ValueError:
            flash("Invalid numeric input for financial fields.", "error")
            return render_template('index.html'), 400

        # Collect other fields
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        business_name = request.form.get('business_name').strip()
        phone_number = request.form.get('phone_number', '').strip()
        first_name = request.form.get('first_name').strip()
        last_name = request.form.get('last_name', '').strip()
        user_type = request.form.get('user_type', '').strip()

        data = [
            timestamp, business_name, income_revenue, expenses_costs, debt_loan,
            debt_interest_rate, auto_email, phone_number, first_name, last_name,
            user_type, email, ""
        ]

        append_to_sheet(data)
        flash("Data submitted successfully! Check your dashboard.", "success")
        return redirect(url_for('dashboard', email=email))

    except Exception as e:
        logger.error(f"Error during form submission: {e}")
        flash(f"Error: {str(e)}", "error")
        return render_template('error.html', message=str(e)), 500

# Dashboard route
@app.route('/dashboard')
def dashboard():
    try:
        email = request.args.get('email', '').strip()
        personalized_message = request.args.get('personalized_message', '')

        if not is_valid_email(email):
            flash("Invalid email provided.", "error")
            return render_template('error.html', message="Invalid email."), 400

        all_users_df = fetch_data_from_sheet()
        if all_users_df.empty:
            flash("No data available.", "error")
            return render_template('error.html', message="No data found."), 404

        all_users_df = calculate_health_score(all_users_df)
        all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
        all_users_df['Rank'] = range(1, len(all_users_df) + 1)

        user_df = all_users_df[all_users_df['Email'] == email]
        if user_df.empty:
            flash("User not found.", "error")
            return render_template('error.html', message="User not found."), 404

        user_row = user_df.iloc[-1]
        health_score = user_row['HealthScore']
        rank = user_row['Rank']
        total_users = len(all_users_df)
        score_description = user_row['ScoreDescription']
        course_title = user_row['CourseTitle']
        course_url = user_row['CourseURL']
        badges = user_row['Badges'].split(",") if user_row['Badges'] and isinstance(user_row['Badges'], str) else []
        first_name = user_row['FirstName']
        last_name = user_row['LastName']

        # Create score breakdown chart
        breakdown_data = {
            "Component": ["Cash Flow", "Debt-to-Income Ratio", "Debt Interest Burden"],
            "Score": [user_row['NormCashFlow'] * 100, user_row['NormDebtToIncome'] * 100, user_row['NormDebtInterest'] * 100]
        }
        breakdown_df = pd.DataFrame(breakdown_data)
        fig_breakdown = px.bar(
            breakdown_df,
            x="Score",
            y="Component",
            orientation='h',
            title="Score Breakdown",
            color="Component",
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
        fig_breakdown.update_layout(showlegend=False)
        breakdown_plot = Markup(fig_breakdown.to_html(full_html=False, include_plotlyjs=False))

        # Create comparison histogram
        fig_comparison = px.histogram(
            all_users_df,
            x='HealthScore',
            nbins=20,
            title="Score Distribution",
            color_discrete_sequence=['#1E88E5']
        )
        fig_comparison.add_vline(
            x=health_score,
            line_color='red',
            line_dash='dash',
            annotation_text="You",
            annotation_position="top right"
        )
        fig_comparison.update_layout(
            xaxis_title="Health Score",
            yaxis_title="Number of Users",
            showlegend=False
        )
        comparison_plot = Markup(fig_comparison.to_html(full_html=False, include_plotlyjs=False))

        return render_template(
            'dashboard.html',
            health_score=health_score,
            rank=int(rank),
            total_users=total_users,
            score_description=score_description,
            course_title=course_title,
            course_url=course_url,
            badges=badges,
            personalized_message=personalized_message,
            breakdown_plot=breakdown_plot,
            comparison_plot=comparison_plot,
            first_name=first_name,
            last_name=last_name,
            email=email,
            newsletter_link="https://forms.gle/3kXnJuDatTm8bT3x7"
        )

    except Exception as e:
        logger.error(f"Error in dashboard: {e}")
        flash(f"Error: {str(e)}", "error")
        return render_template('error.html', message=str(e)), 500

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    flash("Unexpected error occurred.", "error")
    return render_template('error.html', message="Unexpected error occurred."), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Note: To host Plotly.js locally, might download from https://cdn.plot.ly/plotly-latest.min.js first
# Save to static/plotly.min.js and update dashboard.html:
# <script src="{{ url_for('static', filename='plotly.min.js') }}"></script>
