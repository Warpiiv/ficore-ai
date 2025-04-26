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
        logger.info("Data appended to sheet successfully.")
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
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
            logger.info("No data found in Google Sheet.")
            return None
        
        headers = values[0]
        rows = values[1:] if len(values) > 1 else []
        expected_columns = PREDETERMINED_HEADERS
        
        # Log the fetched data
        logger.debug(f"Fetched headers: {headers}")
        logger.debug(f"Fetched rows: {rows}")

        # If headers don't match expected columns, reset the headers
        if headers != expected_columns:
            logger.warning("Headers do not match expected columns. Resetting headers.")
            set_sheet_headers()
            # If there were no rows, return None to indicate the sheet was reset
            if not rows:
                return None
            # Otherwise, adjust the rows to match the expected columns
            normalized_rows = []
            for row in rows:
                if len(row) < len(expected_columns):
                    row = row + [""] * (len(expected_columns) - len(row))
                elif len(row) > len(expected_columns):
                    row = row[:len(expected_columns)]
                normalized_rows.append(row)
            rows = normalized_rows
        
        # Create DataFrame with expected columns
        logger.debug(f"Creating DataFrame with {len(rows)} rows and columns: {expected_columns}")
        df = pd.DataFrame(rows, columns=expected_columns)
        return df
    except Exception as e:
        logger.error(f"Error fetching data from Google Sheet: {e}")
        raise

# Calculate Financial Health Score, determine course suggestion, and assign badges
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

    return badges

# Update badges in Google Sheet
def update_badges_in_sheet(email, new_badges):
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=DATA_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            logger.info("No data found in Google Sheet for badge update.")
            return

        headers = values[0]
        rows = values[1:]
        badge_col_idx = headers.index('Badges')

        # Find all rows for the user
        user_row_indices = [i + 1 for i, row in enumerate(rows) if row[headers.index('Email')] == email]
        if not user_row_indices:
            logger.warning(f"No rows found for email: {email}")
            return

        # Get existing badges from the latest submission
        latest_row_idx = user_row_indices[-1]
        existing_badges = rows[latest_row_idx - 1][badge_col_idx] if badge_col_idx < len(rows[latest_row_idx - 1]) else ""
        existing_badges_list = existing_badges.split(",") if existing_badges else []

        # Combine existing and new badges, removing duplicates
        combined_badges = list(set(existing_badges_list + new_badges))
        if "" in combined_badges:
            combined_badges.remove("")

        # Update all rows for the user with the combined badges
        for row_idx in user_row_indices:
            range_to_update = f'Sheet1!{chr(65 + badge_col_idx)}{row_idx + 1}'
            body = {'values': [[",".join(combined_badges)]]}
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=range_to_update,
                valueInputOption='RAW',
                body=body
            ).execute()
        logger.info(f"Updated badges for email {email}: {combined_badges}")
    except Exception as e:
        logger.error(f"Error updating badges in sheet: {e}")

# Send Email with course suggestion
def send_email(recipient_email, user_name, health_score, score_description, course_title, course_url, rank, total_users):
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    if not sender_email or not sender_password:
        raise Exception("SENDER_EMAIL or SENDER_PASSWORD environment variable not set.")

    # Determine gamified subject line
    top_10_percent = (rank / total_users) <= 0.1
    if top_10_percent:
        subject = "🔥 You're Top 10%! Your Ficore Score Report Awaits!"
    else:
        subject = f"📊 Your Ficore Score Report is Ready, {user_name}!"

    # HTML email body with styled heading, subheading, buttons, and course suggestion
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
            <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem; transition: background-color 0.3s;">{course_title}</a>
        </p>
        <p style="margin-bottom: 10px;">
            Please provide feedback on your experience: 
            <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem; transition: background-color 0.3s;">Feedback Form</a>
        </p>
        <p style="margin-bottom: 10px;">
            Want Smart Insights? Join the waitlist for Ficore Premium: 
            <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #1976D2; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem; transition: background-color 0.3s;">Join Waitlist</a>
        </p>
        <p style="margin-bottom: 10px;">
            Need personalized advice? 
            <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #388E3C; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem; transition: background-color 0.3s;">Book Consultancy</a>
        </p>
        <style>
            a:hover {{
                background-color: #1B5E20 !important; /* Darker green for Feedback and Consultancy buttons */
            }}
            a[href="{WAITLIST_FORM_URL}"]:hover {{
                background-color: #0D47A1 !important; /* Darker blue for Waitlist button */
            }}
            a[href="{course_url}"]:hover {{
                background-color: #F9A825 !important; /* Darker yellow for Course button */
            }}
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
                logger.info(f"Email successfully sent to {recipient_email} (primary email)")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    logger.error(f"Failed to send email to {recipient_email} (primary email) after 3 attempts")
    return False

# Homepage route
@app.route('/')
def home():
    return render_template('index.html')

# Form submission route
@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Extract form data
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        business_name = request.form.get('business_name')
        income_revenue = float(request.form.get('income_revenue').replace(',', ''))
        expenses_costs = float(request.form.get('expenses_costs').replace(',', ''))
        debt_loan = float(request.form.get('debt_loan').replace(',', ''))
        debt_interest_rate = float(request.form.get('debt_interest_rate').replace(',', ''))
        auto_email = request.form.get('auto_email')
        phone_number = request.form.get('phone_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        user_type = request.form.get('user_type')
        email = request.form.get('email')

        if auto_email != email:
            logger.error("Email addresses do not match.")
            return "Error: Email addresses do not match.", 400

        # Prepare data for Google Sheet (with empty Badges column initially)
        data = [
            timestamp, business_name, income_revenue, expenses_costs, debt_loan,
            debt_interest_rate, auto_email, phone_number, first_name, last_name,
            user_type, email, ""  # Empty Badges column
        ]
        # Verify the number of columns matches PREDETERMINED_HEADERS
        if len(data) != len(PREDETERMINED_HEADERS):
            raise ValueError(f"Data column count ({len(data)}) does not match expected headers ({len(PREDETERMINED_HEADERS)}).")
        logger.debug(f"Appending data to sheet: {data}")
        append_to_sheet(data)

        # Fetch updated data
        all_users_df = fetch_data_from_sheet()
        if all_users_df is None:
            logger.warning("No data found in Google Sheet after submission.")
            return render_template('error.html', message="No data found in Google Sheet after submission. Please try again later or contact Ficoreai@outlook.com for support."), 500

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
            logger.warning(f"No data found for user with email: {email}")
            return render_template('error.html', message=f"No data found for user with email: {email}. Please contact Ficoreai@outlook.com for support."), 500

        # Extract user data
        user_row = user_df.iloc[0]
        health_score = user_row['HealthScore']
        rank = user_row['Rank']
        total_users = len(all_users_df)
        score_description = user_row['ScoreDescription']
        course_title = user_row['CourseTitle']
        course_url = user_row['CourseURL']

        # Assign badges
        new_badges = assign_badges(user_df, all_users_df)
        update_badges_in_sheet(email, new_badges)

        # Fetch updated data again to get badges
        all_users_df = fetch_data_from_sheet()
        if all_users_df is None:
            logger.warning("No data found in Google Sheet after updating badges.")
            return render_template('error.html', message="No data found in Google Sheet after updating badges. Please try again later or contact Ficoreai@outlook.com for support."), 500
        user_df = all_users_df[all_users_df['Email'] == email]
        user_row = user_df.iloc[-1]  # Latest submission
        badges = user_row['Badges'].split(",") if user_row['Badges'] else []

        # Generate personalized message
        personalized_message = ""
        if "First Health Score Completed!" in new_badges:
            personalized_message = "🎉 Congratulations, you earned your first badge: Financial Explorer!"
        elif new_badges:
            personalized_message = f"🎉 Great job! You earned a new badge: {new_badges[-1]}"

        # Send email with course suggestion
        user_name = f"{first_name} {last_name}"
        send_email(email, user_name, health_score, score_description, course_title, course_url, rank, total_users)

        # Redirect to dashboard
        return redirect(url_for('dashboard', email=email, personalized_message=personalized_message))
    except ValueError as e:
        logger.error(f"ValueError in form submission: {str(e)}")
        return render_template('error.html', message=f"Invalid input format: {str(e)}. Please ensure all numeric fields contain valid numbers. Contact Ficoreai@outlook.com for support."), 400
    except Exception as e:
        logger.error(f"Error in form submission: {e}")
        return render_template('error.html', message=f"Error processing your submission: {str(e)}. We’re sorry for the inconvenience—please try again later or contact Ficoreai@outlook.com for support."), 500

# Dashboard route
@app.route('/dashboard')
def dashboard():
    try:
        # Get the user's email and personalized message from query parameters
        email = request.args.get('email', 'test@example.com')
        personalized_message = request.args.get('personalized_message', '')

        # Fetch data from Google Sheets
        all_users_df = fetch_data_from_sheet()
        if all_users_df is None:
            logger.warning("No data found in Google Sheet for dashboard.")
            return render_template('error.html', message="No data found in Google Sheet. Please try again later or contact Ficoreai@outlook.com for support."), 500

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
            logger.warning(f"No data found for user with email: {email} in dashboard.")
            return render_template('error.html', message=f"No data found for user with email: {email}. Please contact Ficoreai@outlook.com for support."), 500

        # Extract user data (latest submission)
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
            course_title=course_title,
            course_url=course_url,
            badges=badges,
            personalized_message=personalized_message,
            breakdown_plot=breakdown_plot,
            comparison_plot=comparison_plot
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return render_template('error.html', message=f"Error rendering dashboard: {str(e)}. We’re sorry for the inconvenience—please try again later or contact Ficoreai@outlook.com for support."), 500

if __name__ == "__main__":
    # For Render, bind to 0.0.0.0 and use the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
