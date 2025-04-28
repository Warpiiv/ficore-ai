from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, ValidationError
from flask_caching import Cache
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

# Set secret key for sessions and CSRF
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    raise Exception("FLASK_SECRET_KEY environment variable not set.")

# Configure Flask-Caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Constants for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:M'
RESULTS_SHEET_NAME = 'FicoreAIResults'
RESULTS_HEADER = ['Email', 'FicoreAIScore', 'FicoreAIRank']
FEEDBACK_FORM_URL = 'https://forms.gle/NkiLicSykLyMnhJk7'
WAITLIST_FORM_URL = 'https://forms.gle/3kXnJuDatTm8bT3x7'
CONSULTANCY_FORM_URL = 'https://forms.gle/rfHhpD71MjLpET2K9'
INVESTING_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
SAVINGS_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
DEBT_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
RECOVERY_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email', 'Badges'
]

# Flask-WTF form for submission
class SubmissionForm(FlaskForm):
    business_name = StringField('Business Name', validators=[DataRequired()])
    income_revenue = FloatField('Income Revenue', validators=[DataRequired()])
    expenses_costs = FloatField('Expenses Costs', validators=[DataRequired()])
    debt_loan = FloatField('Debt Loan', validators=[DataRequired()])
    debt_interest_rate = FloatField('Debt Interest Rate', validators=[DataRequired()])
    auto_email = StringField('Auto Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number')
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name')
    user_type = SelectField('User Type', choices=[('Business', 'Business'), ('Individual', 'Individual')], validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Submit')

    def validate_auto_email(self, auto_email):
        if auto_email.data != self.email.data:
            raise ValidationError('Email addresses must match.')

# Authenticate with Google Sheets
def authenticate_google_sheets():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        logger.error("GOOGLE_CREDENTIALS_JSON environment variable not set.")
        return None
    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return build('sheets', 'v4', credentials=creds)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding GOOGLE_CREDENTIALS_JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error authenticating with Google Sheets: {e}")
        return None

# Set Google Sheet headers
def set_sheet_headers():
    try:
        service = authenticate_google_sheets()
        if not service:
            logger.error("Failed to authenticate with Google Sheets.")
            return False
        sheet = service.spreadsheets()
        body = {'values': [PREDETERMINED_HEADERS]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info("Sheet1 headers set to predetermined values.")
        return True
    except Exception as e:
        logger.error(f"Error setting headers: {e}")
        return False

# Get the number of rows in the sheet to determine where to append
def get_row_count():
    try:
        service = authenticate_google_sheets()
        if not service:
            logger.error("Failed to authenticate with Google Sheets.")
            return 0
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        return len(values) if values else 0
    except Exception as e:
        logger.error(f"Error getting row count: {e}")
        return 0

# Append data to Google Sheet with badges included
def append_to_sheet(data):
    try:
        service = authenticate_google_sheets()
        if not service:
            logger.error("Failed to authenticate with Google Sheets.")
            return False
        sheet = service.spreadsheets()

        # Set headers if the sheet is empty
        row_count = get_row_count()
        if row_count == 0:
            if not set_sheet_headers():
                logger.error("Failed to set sheet headers.")
                return False
            row_count = 1  # After setting headers

        # Ensure data matches headers
        if len(data) != len(PREDETERMINED_HEADERS):
            logger.error(f"Data length ({len(data)}) does not match headers ({len(PREDETERMINED_HEADERS)}): {data}")
            return False

        # Append the data
        range_to_update = f'Sheet1!A{row_count + 1}:M{row_count + 1}'
        body = {'values': [data]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info(f"Appended data to sheet at row {row_count + 1}: {data}")
        time.sleep(1)  # Small delay to allow propagation
        return True
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        return False

# Fetch data from Google Sheet with retry mechanism and caching
@cache.memoize(timeout=300)  # Cache for 5 minutes
def fetch_data_from_sheet(max_retries=5, delay=2):
    for attempt in range(max_retries):
        try:
            service = authenticate_google_sheets()
            if not service:
                logger.error("Google Sheets authentication failed.")
                return None
            sheet = service.spreadsheets()
            result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
            values = result.get('values', [])
            
            if not values:
                logger.info(f"Attempt {attempt + 1}: No data found in Google Sheet.")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                    continue
                return pd.DataFrame(columns=PREDETERMINED_HEADERS)
            
            headers = values[0]
            rows = values[1:] if len(values) > 1 else []
            expected_columns = PREDETERMINED_HEADERS
            
            logger.debug(f"Attempt {attempt + 1}: Fetched headers: {headers}")
            logger.debug(f"Attempt {attempt + 1}: Fetched rows: {rows}")

            # If headers don't match, reset headers
            if headers != expected_columns:
                logger.warning(f"Attempt {attempt + 1}: Headers do not match expected columns. Resetting headers.")
                if not set_sheet_headers():
                    logger.error("Failed to reset headers.")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))
                        continue
                    return pd.DataFrame(columns=expected_columns)
                if not rows:
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))
                        continue
                    return pd.DataFrame(columns=expected_columns)
                # Normalize rows
                normalized_rows = []
                for row in rows:
                    if len(row) < len(expected_columns):
                        row = row + [""] * (len(expected_columns) - len(row))
                    elif len(row) > len(expected_columns):
                        row = row[:len(expected_columns)]
                    normalized_rows.append(row)
                rows = normalized_rows
            else:
                # Normalize rows to match headers
                normalized_rows = []
                for row in rows:
                    if len(row) < len(headers):
                        row = row + [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                    normalized_rows.append(row)
                rows = normalized_rows
            
            # Create DataFrame
            if not rows:
                logger.info(f"Attempt {attempt + 1}: No data rows found.")
                df = pd.DataFrame(columns=expected_columns)
            else:
                df = pd.DataFrame(rows, columns=headers)
                for col in expected_columns:
                    if col not in df.columns:
                        df[col] = ""
                df = df[expected_columns]
            
            logger.debug(f"Attempt {attempt + 1}: Created DataFrame with shape {df.shape}")
            return df
        
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: Error fetching data: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
                continue
            return None
    logger.error("Max retries reached while fetching data.")
    return None

# Calculate Financial Health Score
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
    if user_df.empty:
        logger.warning("Empty user_df in assign_badges.")
        return badges
    user_row = user_df.iloc[0]
    email = user_row['Email']
    health_score = user_row['HealthScore']
    current_debt = user_row['DebtLoan']

    user_submissions = all_users_df[all_users_df['Email'] == email]
    if len(user_submissions) <= 1:
        badges.append("First Health Score Completed!")
    if health_score > 80:
        badges.append("Financial Stability Achieved!")
    if len(user_submissions) > 1:
        previous_submission = user_submissions.iloc[-2]
        previous_debt = float(previous_submission['DebtLoan'])
        if current_debt < previous_debt:
            badges.append("Debt Slayer!")

    logger.debug(f"Assigned badges for email {email}: {badges}")
    return badges

# Send Email with course suggestion
def send_email(recipient_email, user_name, health_score, score_description, course_title, course_url, rank, total_users):
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    if not sender_email or not sender_password:
        logger.error("SENDER_EMAIL or SENDER_PASSWORD not set.")
        return False

    top_10_percent = (rank / total_users) <= 0.1
    subject = "🔥 You're Top 10%! Your Ficore Score Report Awaits!" if top_10_percent else f"📊 Your Ficore Score Report is Ready, {user_name}!"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
            <h2 style="color: #FFFFFF; margin: 0;">Ficore AI Financial Health Score</h2>
            <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                Financial growth passport for Africa
            </p>
        </div>
        <p>Dear {user_name},</p>
        <p>We have calculated your Ficore AI Financial Health Score based on your recent submission.</p>
        <ul>
            <li><strong>Score</strong>: {health_score}/100</li>
            <li><strong>Advice</strong>: {score_description}</li>
            <li><strong>Rank</strong>: #{int(rank)} out of {total_users} users</li>
        </ul>
        <p>Follow the advice above to improve your financial health. We’re here to support you every step of the way—take one small action today to grow stronger financially for your business, your goals, and your future!</p>
        <p style="margin-bottom: 10px;">
            Want to learn more? Check out this course: 
            <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">{course_title}</a>
        </p>
        <p style="margin-bottom: 10px;">
            Please provide feedback on your experience: 
            <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Feedback Form</a>
        </p>
        <p style="margin-bottom: 10px;">
            Want Smart Insights? Join the waitlist for Ficore Premium: 
            <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #1976D2; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Join Waitlist</a>
        </p>
        <p style="margin-bottom: 10px;">
            Need personalized advice? 
            <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #388E3C; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Book Consultancy</a>
        </p>
        <style>
            a:hover { background-color: #1B5E20 !important; }
            a[href="{WAITLIST_FORM_URL}"]:hover { background-color: #0D47A1 !important; }
            a[href="{course_url}"]:hover { background-color: #F9A825 !important; }
        </style>
        <p>Best regards,<br>The Ficore AI Team</p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"Ficore AI <{sender_email}>"
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    for attempt in range(3):
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
                logger.info(f"Email sent to {recipient_email}")
                return True
        except Exception as e:
            logger.error(f"Email attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    logger.error(f"Failed to send email to {recipient_email} after 3 attempts")
    return False

# Homepage route
@app.route('/')
def home():
    form = SubmissionForm()
    return render_template('index.html', form=form, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

# Form submission route
@app.route('/submit', methods=['POST'])
def submit():
    form = SubmissionForm()
    try:
        # Log raw POST data for debugging
        raw_data = request.form.to_dict()
        logger.debug(f"Raw POST data: {raw_data}")
        # Log specific financial fields
        logger.debug(f"Received financial fields: income_revenue={raw_data.get('income_revenue')}, "
                    f"expenses_costs={raw_data.get('expenses_costs')}, "
                    f"debt_loan={raw_data.get('debt_loan')}, "
                    f"debt_interest_rate={raw_data.get('debt_interest_rate')}")

        if form.validate_on_submit():
            try:
                # Extract and validate form data
                data = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(form.business_name.data),
                    float(form.income_revenue.data),
                    float(form.expenses_costs.data),
                    float(form.debt_loan.data),
                    float(form.debt_interest_rate.data),
                    str(form.auto_email.data),
                    str(form.phone_number.data or ""),
                    str(form.first_name.data),
                    str(form.last_name.data or ""),
                    str(form.user_type.data),
                    str(form.email.data),
                    ""  # Placeholder for badges
                ]
                logger.debug(f"Form data: {data}")

                # Clear cache to ensure fresh data
                cache.delete_memoized(fetch_data_from_sheet)
                logger.debug("Cleared fetch_data_from_sheet cache")

                # Fetch all users data
                all_users_df = fetch_data_from_sheet()
                if all_users_df is None:
                    logger.error("Failed to fetch data from Google Sheet.")
                    flash("Unable to connect to data storage. Please try again later.", "error")
                    return redirect(url_for('home'))

                # Create temp DataFrame for new submission
                temp_df = pd.DataFrame([data], columns=PREDETERMINED_HEADERS)
                for col in ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)
                
                # Calculate health score and badges
                temp_df = calculate_health_score(temp_df)
                new_badges = assign_badges(temp_df, all_users_df)
                data[-1] = ",".join(new_badges) if new_badges else ""

                # Append data to sheet
                if not append_to_sheet(data):
                    logger.error("Failed to append data to Google Sheet.")
                    flash("Unable to save data. Please try again later.", "error")
                    return redirect(url_for('home'))

                # Fetch updated data
                cache.delete_memoized(fetch_data_from_sheet)
                all_users_df = fetch_data_from_sheet()
                if all_users_df is None or all_users_df.empty:
                    logger.error("No data found in Google Sheet after submission.")
                    flash("Data submission failed. Please try again.", "error")
                    return redirect(url_for('home'))

                # Convert numeric columns
                numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
                for col in numeric_cols:
                    all_users_df[col] = pd.to_numeric(all_users_df[col], errors='coerce').fillna(0)

                # Calculate health scores
                all_users_df = calculate_health_score(all_users_df)

                # Assign ranks
                all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
                all_users_df['Rank'] = range(1, len(all_users_df) + 1)

                # Filter for current user
                user_df = all_users_df[all_users_df['Email'] == form.email.data]
                if user_df.empty:
                    logger.error(f"No data found for email: {form.email.data}")
                    flash("Submission not found. Please try again.", "error")
                    return redirect(url_for('home'))

                # Extract user data
                user_row = user_df.iloc[-1]
                health_score = user_row['HealthScore']
                rank = user_row['Rank']
                total_users = len(all_users_df)
                score_description = user_row['ScoreDescription']
                course_title = user_row['CourseTitle']
                course_url = user_row['CourseURL']
                badges = user_row['Badges'].split(",") if user_row['Badges'] else []

                # Generate personalized message
                personalized_message = ""
                if "First Health Score Completed!" in new_badges:
                    personalized_message = "🎉 Congratulations, you earned your first badge: Financial Explorer!"
                elif new_badges:
                    personalized_message = f"🎉 Great job! You earned a new badge: {new_badges[-1]}"

                # Send email
                user_name = f"{form.first_name.data} {form.last_name.data}".strip()
                email_sent = send_email(form.email.data, user_name, health_score, score_description, course_title, course_url, rank, total_users)
                if not email_sent:
                    personalized_message += " ⚠️ Unable to send email report. Please check your spam folder or contact support."

                flash("Data submitted successfully!", "success")
                return redirect(url_for('dashboard', email=form.email.data, personalized_message=personalized_message))
            except ValueError as e:
                logger.error(f"ValueError in submission: {e}")
                flash(f"Invalid input: {str(e)}. Please ensure all numeric fields contain valid numbers.", "error")
                return redirect(url_for('home'))
            except Exception as e:
                logger.error(f"Submission error: {e}")
                flash(f"Submission failed: {str(e)}. Please try again or contact support.", "error")
                return redirect(url_for('home'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    logger.warning(f"Form validation error in {field}: {error}")
                    flash(f"Error in {field}: {error}", "error")
            return redirect(url_for('home'))
    except ImportError as e:
        logger.error(f"Email validation error: {e}")
        flash("Email validation setup error. Please contact Ficoreai@outlook.com for support.", "error")
        return redirect(url_for('home'))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    try:
        email = request.args.get('email', 'test@example.com')
        personalized_message = request.args.get('personalized_message', '')

        all_users_df = fetch_data_from_sheet()
        if all_users_df is None or all_users_df.empty:
            logger.error("No data found in Google Sheet for dashboard.")
            flash("No data found. Please try again later.", "error")
            return redirect(url_for('home'))

        numeric_cols = ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']
        for col in numeric_cols:
            all_users_df[col] = pd.to_numeric(all_users_df[col], errors='coerce').fillna(0)

        all_users_df = calculate_health_score(all_users_df)
        all_users_df = all_users_df.sort_values(by='HealthScore', ascending=False)
        all_users_df['Rank'] = range(1, len(all_users_df) + 1)

        user_df = all_users_df[all_users_df['Email'] == email]
        if user_df.empty:
            logger.error(f"No data found for email: {email}")
            flash(f"No data found for email: {email}.", "error")
            return redirect(url_for('home'))

        user_row = user_df.iloc[-1]
        if not user_row['Badges']:
            user_df = calculate_health_score(user_df)
            new_badges = assign_badges(user_df, all_users_df)
            user_df['Badges'] = ",".join(new_badges)

        user_row = user_df.iloc[-1]
        health_score = user_row['HealthScore']
        rank = user_row['Rank']
        total_users = len(all_users_df)
        score_description = user_row['ScoreDescription']
        course_title = user_row['CourseTitle']
        course_url = user_row['CourseURL']
        badges = user_row['Badges'].split(",") if user_row['Badges'] else []
        cash_flow_score = round(user_row['NormCashFlow'] * 100, 2)
        debt_to_income_score = round(user_row['NormDebtToIncome'] * 100, 2)
        debt_interest_score = round(user_row['NormDebtInterest'] * 100, 2)
        first_name = user_row['FirstName']
        email = user_row['Email']

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
            email=email,
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash(f"Error loading dashboard: {str(e)}. Please try again or contact support.", "error")
        return redirect(url_for('home'))

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    flash("An unexpected error occurred. Please try again or contact support.", "error")
    return redirect(url_for('home'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
