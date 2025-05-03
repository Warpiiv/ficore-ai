from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, EmailField, TelField
from wtforms.validators import DataRequired, Email, EqualTo, Optional
import plotly.graph_objs as go
from plotly.utils import PlotlyJSONEncoder
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
import re
from datetime import datetime, timedelta
from dateutil.parser import parse
from translations import translations
import pandas as pd
import traceback

app = Flask(__name__, template_folder='ficore_templates', static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'x7k9m2p8q3w5z6t4r1y0n3j8h5f2d4g')
app.config['SESSION_TYPE'] = 'filesystem'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    language = session.get('language', 'English')
    logger.error(f"404 error: {str(e)}")
    return render_template('404.html', translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL), 404

@app.errorhandler(500)
def internal_server_error(e):
    language = session.get('language', 'English')
    logger.error(f"500 error: {str(e)}\n{traceback.format_exc()}")
    return render_template('500.html', translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL), 500

@app.errorhandler(405)
def method_not_allowed(e):
    language = session.get('language', 'English')
    logger.error(f"405 error: {str(e)}")
    flash(translations[language]['Method Not Allowed'], 'error')
    return redirect(url_for('landing'))

# Constants
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I"
FEEDBACK_FORM_URL = "https://forms.gle/NkiLicSykLyMnhJk7"
WAITLIST_FORM_URL = "https://forms.gle/3kXnJuDatTm8bT3x7"
CONSULTANCY_FORM_URL = "https://forms.gle/rfHhpD71MjLpET2K9"
INVESTING_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
SAVINGS_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
DEBT_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
RECOVERY_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"

SHEET_NAMES = {
    'index': 'IndexSheet',
    'net_worth': 'NetWorthSheet',
    'emergency_fund': 'EmergencyFundSheet',
    'quiz': 'QuizSheet',
    'budget': 'BudgetSheet',
    'expense_tracker': 'ExpenseTrackerSheet',
    'bill_planner': 'BillPlannerSheet'
}

PREDETERMINED_HEADERS = {
    'index': [
        'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
        'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName',
        'UserType', 'Email', 'Badges', 'Language', 'HealthScore'
    ],
    'net_worth': [
        'Timestamp', 'FirstName', 'Email', 'Language', 'Assets', 'Liabilities', 'NetWorth'
    ],
    'emergency_fund': [
        'Timestamp', 'FirstName', 'Email', 'Language', 'MonthlyExpenses', 'EmergencyFund'
    ],
    'quiz': [
        'Timestamp', 'FirstName', 'Email', 'Language', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'QuizScore'
    ],
    'budget': [
        'Timestamp', 'FirstName', 'Email', 'AutoEmail', 'Language', 'MonthlyIncome',
        'HousingExpenses', 'FoodExpenses', 'TransportExpenses', 'OtherExpenses',
        'TotalExpenses', 'SurplusDeficit'
    ],
    'expense_tracker': [
        'Timestamp', 'FirstName', 'Email', 'Language', 'Amount', 'Description',
        'Category', 'TransactionType', 'RunningBalance'
    ],
    'bill_planner': [
        'Timestamp', 'FirstName', 'Email', 'Language', 'Description', 'Amount',
        'DueDate', 'Category', 'Recurrence', 'Status'
    ]
}

# Email configuration
EMAIL_ADDRESS = os.getenv('SMTP_USER')
EMAIL_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# Google Sheets setup
try:
    credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if not credentials_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON environment variable not set")
    credentials_dict = json.loads(credentials_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    logger.info("Successfully connected to Google Sheets database")
except Exception as e:
    logger.error(f"Failed to connect to Google Sheets: {str(e)}")
    raise Exception("Database connection failed")

def setup_sheets():
    try:
        existing_sheets = [s.title for s in spreadsheet.worksheets()]
        for feature, sheet_name in SHEET_NAMES.items():
            if sheet_name not in existing_sheets:
                spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=len(PREDETERMINED_HEADERS[feature]))
                logger.info(f"Created sheet: {sheet_name}")
            worksheet = spreadsheet.worksheet(sheet_name)
            current_headers = worksheet.row_values(1)
            if not current_headers or current_headers != PREDETERMINED_HEADERS[feature]:
                worksheet.clear()
                worksheet.append_row(PREDETERMINED_HEADERS[feature])
                logger.info(f"Set headers for {sheet_name}: {PREDETERMINED_HEADERS[feature]}")
    except Exception as e:
        logger.error(f"Error setting up sheets: {str(e)}")
        raise

setup_sheets()

# Forms
class SubmissionForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name')
    email = EmailField('Email', validators=[DataRequired(), Email()])
    auto_email = EmailField('Confirm Email', validators=[DataRequired(), Email(), EqualTo('email')])
    phone_number = TelField('Phone Number')
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    business_name = StringField('Business Name', validators=[DataRequired()])
    user_type = SelectField('User Type', choices=[('Business', 'Business'), ('Individual', 'Individual')], default='Business')
    income_revenue = StringField('Income/Revenue', validators=[DataRequired()])
    expenses_costs = StringField('Expenses/Costs', validators=[DataRequired()])
    debt_loan = StringField('Debt/Loan', validators=[DataRequired()])
    debt_interest_rate = StringField('Debt Interest Rate', validators=[DataRequired()])
    submit = SubmitField('Submit')

class NetWorthForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    assets = StringField('Assets', validators=[DataRequired()])
    liabilities = StringField('Liabilities', validators=[DataRequired()])
    submit = SubmitField('Submit')

class EmergencyFundForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    monthly_expenses = StringField('Monthly Expenses', validators=[DataRequired()])
    submit = SubmitField('Submit')

class QuizForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    q1 = SelectField('Question 1', choices=[('', 'Select'), ('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q2 = SelectField('Question 2', choices=[('', 'Select'), ('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q3 = SelectField('Question 3', choices=[('', 'Select'), ('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q4 = SelectField('Question 4', choices=[('', 'Select'), ('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    q5 = SelectField('Question 5', choices=[('', 'Select'), ('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    submit = SubmitField('Submit')

class BudgetForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    auto_email = EmailField('Receive Budgeting Tips via Email (Optional)')
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    monthly_income = StringField('Monthly Income', validators=[DataRequired()])
    housing_expenses = StringField('Housing Expenses', validators=[DataRequired()])
    food_expenses = StringField('Food Expenses', validators=[DataRequired()])
    transport_expenses = StringField('Transport Expenses', validators=[DataRequired()])
    other_expenses = StringField('Other Expenses', validators=[DataRequired()])
    submit = SubmitField('Submit')

class ExpenseForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    amount = StringField('Amount', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('', 'Select'), ('Housing', 'Housing'), ('Food', 'Food'), ('Transport', 'Transport'),
        ('Entertainment', 'Entertainment'), ('Utilities', 'Utilities'), ('Other', 'Other')
    ], validators=[DataRequired()])
    transaction_type = SelectField('Transaction Type', choices=[
        ('', 'Select'), ('Income', 'Income'), ('Expense', 'Expense')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit')

class BillForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], default='English')
    description = StringField('Description', validators=[DataRequired()])
    amount = StringField('Amount', validators=[Optional()])
    due_date = StringField('Due Date', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('', 'Select'), ('Housing', 'Housing'), ('Food', 'Food'), ('Transport', 'Transport'),
        ('Utilities', 'Utilities'), ('Other', 'Other')
    ], validators=[DataRequired()])
    recurrence = SelectField('Recurrence', choices=[
        ('None', 'None'), ('Weekly', 'Weekly'), ('Monthly', 'Monthly')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit')

# Helper functions
def send_email(to_email, subject, body, language):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def generate_chart(data, title):
    try:
        fig = go.Figure(data=[go.Pie(labels=list(data.keys()), values=list(data.values()))])
        fig.update_layout(title_text=title, margin=dict(l=20, r=20, t=40, b=20), height=300)
        chart_json = json.dumps(fig, cls=PlotlyJSONEncoder)
        return chart_json
    except Exception as e:
        logger.error(f"Error generating chart: {str(e)}")
        return None

def calculate_health_score(df):
    try:
        if df.empty:
            return df
        df['IncomeRevenueSafe'] = df['IncomeRevenue'].apply(lambda x: float(re.sub(r'[,]', '', str(x))) if str(x).replace(',', '').strip() else 1e-10)
        df['ExpensesCosts'] = df['ExpensesCosts'].apply(lambda x: float(re.sub(r'[,]', '', str(x))) if str(x).replace(',', '').strip() else 0.0)
        df['DebtLoan'] = df['DebtLoan'].apply(lambda x: float(re.sub(r'[,]', '', str(x))) if str(x).replace(',', '').strip() else 0.0)
        df['DebtInterestRate'] = df['DebtInterestRate'].apply(lambda x: float(re.sub(r'[,]', '', str(x))) if str(x).replace(',', '').strip() else 0.0)
        df['CashFlowRatio'] = (df['IncomeRevenueSafe'] - df['ExpensesCosts']) / df['IncomeRevenueSafe']
        df['DebtToIncomeRatio'] = df['DebtLoan'] / df['IncomeRevenueSafe']
        df['DebtInterestBurden'] = df['DebtInterestRate'].clip(lower=0) / 20
        df['DebtInterestBurden'] = df['DebtInterestBurden'].clip(upper=1)
        df['NormCashFlow'] = df['CashFlowRatio'].clip(0, 1)
        df['NormDebtToIncome'] = 1 - df['DebtToIncomeRatio'].clip(0, 1)
        df['NormDebtInterest'] = 1 - df['DebtInterestBurden']
        df['HealthScore'] = (df['NormCashFlow'] * 0.333 + df['NormDebtToIncome'] * 0.333 + df['NormDebtInterest'] * 0.333) * 100
        df['HealthScore'] = df['HealthScore'].round(2)

        def score_description_and_course(row):
            score = row['HealthScore']
            cash_flow = row['CashFlowRatio']
            debt_to_income = row['DebtToIncomeRatio']
            debt_interest = row['DebtInterestBurden']
            if score >= 75:
                return ('Stable Income; invest excess now', INVESTING_COURSE_URL)
            elif score >= 50:
                if cash_flow < 0.3 or debt_interest > 0.5:
                    return ('At Risk; manage your expense!', DEBT_COURSE_URL)
                return ('Moderate; save something monthly!', SAVINGS_COURSE_URL)
            elif score >= 25:
                if debt_to_income > 0.5 or debt_interest > 0.5:
                    return ('At Risk; pay off debt, manage your expense!', DEBT_COURSE_URL)
                return ('At Risk; manage your expense!', DEBT_COURSE_URL)
            else:
                if debt_to_income > 0.5 or cash_flow < 0.3:
                    return ('Critical; add source of income! pay off debt! manage your expense!', RECOVERY_COURSE_URL)
                return ('Critical; seek financial help and advice!', RECOVERY_COURSE_URL)

        df[['ScoreDescription', 'CourseURL']] = [score_description_and_course(row) for _, row in df.iterrows()]
        return df
    except Exception as e:
        logger.error(f"Error calculating health score: {str(e)}")
        raise

def assign_badges(user_df, all_users_df, language):
    badges = []
    if user_df.empty:
        logger.warning("User DataFrame is empty, no badges assigned")
        return badges
    
    user_row = user_df.iloc[0]
    if len(user_df) == 1:
        badge_key = 'First Health Score Completed!'
        badge_text = translations.get(language, {}).get(badge_key, badge_key)
        badges.append(badge_text)
        if badge_text == badge_key:
            logger.warning(f"Translation missing for '{badge_key}' in language '{language}'")
    
    if user_row['HealthScore'] >= 50:
        badge_key = 'Financial Stability Achieved!'
        badge_text = translations.get(language, {}).get(badge_key, badge_key)
        badges.append(badge_text)
        if badge_text == badge_key:
            logger.warning(f"Translation missing for '{badge_key}' in language '{language}'")
    
    if user_row['DebtToIncomeRatio'] < 0.3:
        badge_key = 'Debt Slayer!'
        badge_text = translations.get(language, {}).get(badge_key, badge_key)
        badges.append(badge_text)
        if badge_text == badge_key:
            logger.warning(f"Translation missing for '{badge_key}' in language '{language}'")
    
    logger.info(f"Assigned badges: {badges} for user with email {user_row['Email']}")
    return badges

def save_to_google_sheets(feature, data):
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES[feature])
        worksheet.append_row(list(data.values()))
        logger.info(f"Data saved to Google Sheets ({SHEET_NAMES[feature]}): {data}")
    except Exception as e:
        logger.error(f"Error saving to Google Sheets ({SHEET_NAMES[feature]}): {str(e)}")
        raise

def get_rank_from_db(feature, value, column_name):
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES[feature])
        all_data = worksheet.get_all_records()
        values = [float(row[column_name]) for row in all_data if row[column_name]]
        if not values:
            return 50
        rank = sum(1 for v in values if v < value) / len(values) * 100
        return min(100, max(0, int(rank)))
    except Exception as e:
        logger.error(f"Error calculating rank ({SHEET_NAMES[feature]}): {str(e)}")
        return 50

def get_advice(value, language):
    if value > 0:
        return translations[language].get('Positive Value Advice', 'Your positive value indicates financial progress.')
    elif value == 0:
        return translations[language].get('Zero Value Advice', 'Your value is zero. Review your inputs.')
    else:
        return translations[language].get('Negative Value Advice', 'A negative value suggests financial challenges.')

def get_badges(value, language):
    badges = []
    if value > 1000:
        badges.append(translations[language].get('High Value Badge', 'High Value Badge'))
    if value > 0:
        badges.append(translations[language].get('Positive Value Badge', 'Positive Value Badge'))
    return badges

def get_tips(language):
    return [
        translations[language].get('Tip 1', 'Create a budget to track your income and expenses.'),
        translations[language].get('Tip 2', 'Build an emergency fund to cover unexpected costs.'),
        translations[language].get('Tip 3', 'Pay off high-interest debt to reduce financial stress.')
    ]

def get_courses(language):
    return [
        {'title': translations[language].get('Course 1 Title', 'Introduction to Financial Planning'), 'link': INVESTING_COURSE_URL},
        {'title': translations[language].get('Course 2 Title', 'Debt Management Basics'), 'link': SAVINGS_COURSE_URL}
    ]

def suggest_category(description):
    desc = description.lower()
    if any(word in desc for word in ['transport', 'fuel', 'bus', 'taxi']):
        return 'Transport'
    elif any(word in desc for word in ['food', 'groceries', 'dining', 'meal']):
        return 'Food'
    elif any(word in desc for word in ['rent', 'mortgage', 'utilities', 'electricity', 'water']):
        return 'Housing'
    elif any(word in desc for word in ['entertainment', 'subscription', 'movie', 'music']):
        return 'Entertainment'
    elif any(word in desc for word in ['bill', 'phone', 'internet']):
        return 'Utilities'
    return 'Other'

def parse_natural_date(text):
    try:
        parsed_date = parse(text, fuzzy=True, dayfirst=True)
        return parsed_date.strftime('%Y-%m-%d')
    except ValueError:
        return None

def calculate_running_balance(transactions):
    balance = 0
    for transaction in transactions:
        amount = float(transaction['Amount'])
        if transaction['TransactionType'] == 'Income':
            balance += amount
        else:
            balance -= amount
        transaction['RunningBalance'] = str(balance)
    return transactions

def generate_insight(transactions, language):
    if not transactions:
        return None
    df = pd.DataFrame(transactions)
    df['Amount'] = df['Amount'].astype(float)
    week_ago = datetime.now() - timedelta(days=7)
    recent = df[df['Timestamp'] >= week_ago.strftime('%Y-%m-%d %H:%M:%S')]
    if recent.empty:
        return None
    total_expense = recent[recent['TransactionType'] == 'Expense']['Amount'].sum()
    top_category = recent[recent['TransactionType'] == 'Expense'].groupby('Category')['Amount'].sum().idxmax() if not recent[recent['TransactionType'] == 'Expense'].empty else None
    if top_category:
        return translations[language].get('Insight', 'Insight') + f": ₦{total_expense:.2f} spent this week, mostly on {top_category}."
    return None

# Routes
@app.route('/', methods=['GET', 'HEAD'])
def landing():
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    logger.info(f"Rendering landing page with language: {language}")

    if request.method == 'HEAD':
        return '', 200

    return render_template('landing.html', translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

@app.route('/set_language', methods=['POST'])
def set_language():
    language = request.form.get('language', 'English')
    if language in ['English', 'Hausa']:
        session['language'] = language
        logger.info(f"Language set to: {language}")
    else:
        logger.warning(f"Invalid language selected: {language}. Defaulting to English.")
        session['language'] = 'English'
    return redirect(url_for('landing'))

@app.route('/financial_health', methods=['GET', 'POST', 'HEAD'])
def financial_health():
    form = SubmissionForm()
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    logger.info(f"Rendering financial health form with language: {language}")

    if request.method == 'HEAD':
        return '', 200

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                for field in ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate']:
                    value = float(re.sub(r'[,]', '', form[field].data))
                    if value < 0:
                        flash(translations[language]['Invalid Number'], 'error')
                        return render_template('index.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
            except ValueError:
                flash(translations[language]['Invalid Number'], 'error')
                return render_template('index.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

            session['language'] = form.language.data
            return redirect(url_for('submit'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'error')
            return render_template('index.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

    return render_template('index.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    if request.method == 'GET':
        flash(translations[language]['Please submit the financial health form to view your dashboard.'], 'info')
        return redirect(url_for('financial_health'))

    form = SubmissionForm()
    if form.validate_on_submit():
        try:
            income_revenue = float(re.sub(r'[,]', '', form.income_revenue.data))
            expenses_costs = float(re.sub(r'[,]', '', form.expenses_costs.data))
            debt_loan = float(re.sub(r'[,]', '', form.debt_loan.data))
            debt_interest_rate = float(re.sub(r'[,]', '', form.debt_interest_rate.data))
            if any(v < 0 for v in [income_revenue, expenses_costs, debt_loan, debt_interest_rate]):
                flash(translations[language]['Invalid Number'], 'error')
                return redirect(url_for('financial_health'))
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return redirect(url_for('financial_health'))

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = {
            'Timestamp': timestamp,
            'BusinessName': form.business_name.data,
            'IncomeRevenue': form.income_revenue.data,
            'ExpensesCosts': form.expenses_costs.data,
            'DebtLoan': form.debt_loan.data,
            'DebtInterestRate': form.debt_interest_rate.data,
            'AutoEmail': form.auto_email.data,
            'PhoneNumber': form.phone_number.data,
            'FirstName': form.first_name.data,
            'LastName': form.last_name.data,
            'UserType': form.user_type.data,
            'Email': form.email.data,
            'Badges': '',
            'Language': form.language.data,
            'HealthScore': ''
        }
        save_to_google_sheets('index', data)

        worksheet = spreadsheet.worksheet(SHEET_NAMES['index'])
        all_data = worksheet.get_all_records()
        df = calculate_health_score(pd.DataFrame(all_data))
        user_df = df[df['Email'] == form.email.data].copy()
        if user_df.empty:
            user_df = pd.DataFrame([data], columns=PREDETERMINED_HEADERS['index'])
            user_df = calculate_health_score(user_df)
        all_users_df = df.copy()

        badges = assign_badges(user_df, all_users_df, language)
        user_df.at[user_df.index[0], 'Badges'] = ','.join(badges)
        worksheet.update_cell(len(all_data) + 2, 13, ','.join(badges))

        all_users_df = all_users_df.sort_values('HealthScore', ascending=False).reset_index(drop=True)
        user_index = all_users_df.index[all_users_df['Email'] == form.email.data].tolist()[0]
        rank = user_index + 1
        total_users = len(all_users_df.drop_duplicates(subset=['Email']))

        health_score = user_df['HealthScore'].iloc[0]
        score_description = user_df['ScoreDescription'].iloc[0]
        course_url = user_df['CourseURL'].iloc[0]

        user_data = {
            'income': income_revenue,
            'expenses': expenses_costs,
            'debt': debt_loan
        }
        peer_data = {'averageScore': all_users_df['HealthScore'].mean() if not all_users_df.empty else 50.0}

        breakdown_data = {
            'Cash Flow': user_df['NormCashFlow'].iloc[0] * 100 / 3,
            'Debt-to-Income': user_df['NormDebtToIncome'].iloc[0] * 100 / 3,
            'Debt Interest': user_df['NormDebtInterest'].iloc[0] * 100 / 3
        }
        breakdown_chart = generate_chart(breakdown_data, translations[language]['Score Breakdown'])
        comparison_chart = generate_chart({'You': health_score, 'Peers': peer_data['averageScore']}, translations[language]['Comparison to Peers'])

        email_body = translations[language]['Email Body'].format(
            user_name=form.first_name.data,
            health_score=health_score,
            score_description=score_description,
            rank=rank,
            total_users=total_users,
            course_url=course_url,
            course_title=translations[language]['Recommended Course'],
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
        )
        if send_email(form.email.data, translations[language]['Score Report Subject'].format(user_name=form.first_name.data), email_body, language):
            flash(translations[language]['Email sent successfully'], 'success')
        else:
            flash(translations[language]['Failed to send email'], 'error')

        session['language'] = form.language.data
        session['full_name'] = form.first_name.data

        flash(translations[language]['Submission Success'], 'success')
        return render_template(
            'dashboard.html',
            first_name=form.first_name.data,
            last_name=form.last_name.data or '',
            email=form.email.data,
            user_data=user_data,
            health_score=health_score,
            peer_data=peer_data,
            rank=rank,
            total_users=total_users,
            badges=badges,
            course_title=translations[language]['Recommended Course'],
            course_url=course_url,
            breakdown_chart=breakdown_chart,
            comparison_chart=comparison_chart,
            personalized_message=score_description,
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL,
            translations=translations,
            language=language
        )
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'error')
        return redirect(url_for('financial_health'))

@app.route('/net_worth', methods=['GET', 'POST'])
def net_worth():
    form = NetWorthForm()
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                try:
                    assets = float(re.sub(r'[,]', '', form.assets.data))
                    liabilities = float(re.sub(r'[,]', '', form.liabilities.data))
                    if assets < 0 or liabilities < 0:
                        flash(translations[language]['Invalid Number'], 'error')
                        return render_template('net_worth_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
                except ValueError:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('net_worth_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                net_worth = assets - liabilities
                data = {
                    'Timestamp': timestamp,
                    'FirstName': form.first_name.data,
                    'Email': form.email.data,
                    'Language': form.language.data,
                    'Assets': form.assets.data,
                    'Liabilities': form.liabilities.data,
                    'NetWorth': str(net_worth)
                }
                save_to_google_sheets('net_worth', data)

                advice = get_advice(net_worth, language)
                badges = get_badges(net_worth, language)
                tips = get_tips(language)
                courses = get_courses(language)

                breakdown_data = {'Assets': assets, 'Liabilities': liabilities}
                breakdown_chart = generate_chart(breakdown_data, translations[language].get('Asset-Liability Breakdown', 'Asset-Liability Breakdown'))

                rank = get_rank_from_db('net_worth', net_worth, 'NetWorth')
                total_users = len(spreadsheet.worksheet(SHEET_NAMES['net_worth']).get_all_records())

                session['language'] = form.language.data
                flash(translations[language]['Submission Success'], 'success')
                return render_template(
                    'net_worth_dashboard.html',
                    first_name=form.first_name.data,
                    email=form.email.data,
                    net_worth=net_worth,
                    advice=advice,
                    badges=badges,
                    tips=tips,
                    courses=courses,
                    breakdown_chart=breakdown_chart,
                    rank=rank,
                    total_users=total_users,
                    FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                    translations=translations,
                    language=language
                )
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return render_template('net_worth_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        return render_template('net_worth_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
    except Exception as e:
        logger.error(f"Error in net_worth route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/emergency_fund', methods=['GET', 'POST'])
def emergency_fund():
    form = EmergencyFundForm()
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                try:
                    monthly_expenses = float(re.sub(r'[,]', '', form.monthly_expenses.data))
                    if monthly_expenses < 0:
                        flash(translations[language]['Invalid Number'], 'error')
                        return render_template('emergency_fund_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
                except ValueError:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('emergency_fund_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                emergency_fund = monthly_expenses * 6
                data = {
                    'Timestamp': timestamp,
                    'FirstName': form.first_name.data,
                    'Email': form.email.data,
                    'Language': form.language.data,
                    'MonthlyExpenses': form.monthly_expenses.data,
                    'EmergencyFund': str(emergency_fund)
                }
                save_to_google_sheets('emergency_fund', data)

                advice = translations[language].get('Tip 2', 'Build an emergency fund to cover unexpected costs.')
                tips = get_tips(language)
                courses = get_courses(language)

                breakdown_data = {'Monthly Expenses': monthly_expenses, 'Emergency Fund (6 months)': emergency_fund}
                breakdown_chart = generate_chart(breakdown_data, translations[language].get('Expense-Fund Breakdown', 'Expense-Fund Breakdown'))

                rank = get_rank_from_db('emergency_fund', emergency_fund, 'EmergencyFund')
                total_users = len(spreadsheet.worksheet(SHEET_NAMES['emergency_fund']).get_all_records())

                session['language'] = form.language.data
                flash(translations[language]['Submission Success'], 'success')
                return render_template(
                    'emergency_fund_dashboard.html',
                    first_name=form.first_name.data,
                    email=form.email.data,
                    emergency_fund=emergency_fund,
                    monthly_expenses=monthly_expenses,
                    advice=advice,
                    tips=tips,
                    courses=courses,
                    breakdown_chart=breakdown_chart,
                    rank=rank,
                    total_users=total_users,
                    FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                    translations=translations,
                    language=language
                )
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return render_template('emergency_fund_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        return render_template('emergency_fund_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
    except Exception as e:
        logger.error(f"Error in emergency_fund route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    form = QuizForm()
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                answers = [form.q1.data, form.q2.data, form.q3.data, form.q4.data, form.q5.data]
                quiz_score = sum(20 for answer in answers if answer.lower() == 'yes')

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data = {
                    'Timestamp': timestamp,
                    'FirstName': form.first_name.data,
                    'Email': form.email.data,
                    'Language': form.language.data,
                    'Q1': form.q1.data,
                    'Q2': form.q2.data,
                    'Q3': form.q3.data,
                    'Q4': form.q4.data,
                    'Q5': form.q5.data,
                    'QuizScore': str(quiz_score)
                }
                save_to_google_sheets('quiz', data)

                advice = translations[language].get('Test your financial knowledge and get personalized tips.', 'Test your financial knowledge.')
                tips = get_tips(language)
                courses = get_courses(language)

                performance_data = {f'Question {i+1}': (20 if ans.lower() == 'yes' else 0) for i, ans in enumerate(answers)}
                performance_chart = generate_chart(performance_data, translations[language].get('Question Performance', 'Question Performance'))

                rank = get_rank_from_db('quiz', quiz_score, 'QuizScore')
                total_users = len(spreadsheet.worksheet(SHEET_NAMES['quiz']).get_all_records())

                session['language'] = form.language.data
                flash(translations[language]['Submission Success'], 'success')
                return render_template(
                    'quiz_dashboard.html',
                    first_name=form.first_name.data,
                    email=form.email.data,
                    quiz_score=quiz_score,
                    advice=advice,
                    tips=tips,
                    courses=courses,
                    performance_chart=performance_chart,
                    rank=rank,
                    total_users=total_users,
                    FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                    translations=translations,
                    language=language
                )
            else:
                flash(translations[language]['Please answer all questions before submitting!'], 'error')
                return render_template('quiz_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        return render_template('quiz_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
    except Exception as e:
        logger.error(f"Error in quiz route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/budget', methods=['GET', 'POST'])
def budget():
    form = BudgetForm()
    language = session.get('language', 'English')
    if language not in translations:
        logger.warning(f"Invalid language in session: {language}. Defaulting to English.")
        language = 'English'
        session['language'] = language

    try:
        if request.method == 'POST':
            if form.validate_on_submit():
                try:
                    monthly_income = float(re.sub(r'[,]', '', form.monthly_income.data))
                    housing_expenses = float(re.sub(r'[,]', '', form.housing_expenses.data))
                    food_expenses = float(re.sub(r'[,]', '', form.food_expenses.data))
                    transport_expenses = float(re.sub(r'[,]', '', form.transport_expenses.data))
                    other_expenses = float(re.sub(r'[,]', '', form.other_expenses.data))
                    if any(v < 0 for v in [monthly_income, housing_expenses, food_expenses, transport_expenses, other_expenses]):
                        flash(translations[language]['Invalid Number'], 'error')
                        return render_template('budget_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
                except ValueError:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('budget_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

                total_expenses = housing_expenses + food_expenses + transport_expenses + other_expenses
                surplus_deficit = monthly_income - total_expenses

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data = {
                    'Timestamp': timestamp,
                    'FirstName': form.first_name.data,
                    'Email': form.email.data,
                    'AutoEmail': form.auto_email.data or '',
                    'Language': form.language.data,
                    'MonthlyIncome': form.monthly_income.data,
                    'HousingExpenses': form.housing_expenses.data,
                    'FoodExpenses': form.food_expenses.data,
                    'TransportExpenses': form.transport_expenses.data,
                    'OtherExpenses': form.other_expenses.data,
                    'TotalExpenses': str(total_expenses),
                    'SurplusDeficit': str(surplus_deficit)
                }
                save_to_google_sheets('budget', data)

                advice = get_advice(surplus_deficit, language)
                tips = get_tips(language)
                courses = get_courses(language)

                breakdown_data = {
                    'Housing': housing_expenses,
                    'Food': food_expenses,
                    'Transport': transport_expenses,
                    'Other': other_expenses
                }
                breakdown_chart = generate_chart(breakdown_data, translations[language].get('Expense Breakdown', 'Expense Breakdown'))

                rank = get_rank_from_db('budget', surplus_deficit, 'SurplusDeficit')
                total_users = len(spreadsheet.worksheet(SHEET_NAMES['budget']).get_all_records())

                session['language'] = form.language.data
                flash(translations[language]['Submission Success'], 'success')
                return render_template(
                    'budget_dashboard.html',
                    first_name=form.first_name.data,
                    email=form.email.data,
                    monthly_income=monthly_income,
                    total_expenses=total_expenses,
                    surplus_deficit=surplus_deficit,
                    advice=advice,
                    tips=tips,
                    courses=courses,
                    breakdown_chart=breakdown_chart,
                    rank=rank,
                    total_users=total_users,
                    FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                    translations=translations,
                    language=language
                )
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return render_template('budget_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        return render_template('budget_form.html', form=form, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
    except Exception as e:
        logger.error(f"Error in budget route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/expense_tracker', methods=['GET', 'POST'])
def expense_tracker():
    form = ExpenseForm()
    language = session.get('language', 'English')
    if language not in translations:
        language = 'English'
        session['language'] = language

    try:
        transactions = session.get('transactions', [])
        if request.method == 'POST' and form.validate_on_submit():
            try:
                amount = float(re.sub(r'[,]', '', form.amount.data))
                if amount < 0:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('expense_tracker.html', form=form, transactions=transactions, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)
            except ValueError:
                flash(translations[language]['Invalid Number'], 'error')
                return render_template('expense_tracker.html', form=form, transactions=transactions, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            transaction = {
                'Timestamp': timestamp,
                'FirstName': form.first_name.data,
                'Email': form.email.data,
                'Language': form.language.data,
                'Amount': str(amount),
                'Description': form.description.data,
                'Category': form.category.data,
                'TransactionType': form.transaction_type.data,
                'RunningBalance': '0'
            }
            transactions.append(transaction)
            transactions = calculate_running_balance(transactions)
            session['transactions'] = transactions

            save_to_google_sheets('expense_tracker', transaction)
            insight = generate_insight(transactions, language)
            flash(translations[language]['Transaction Added'], 'success')
            return render_template('expense_tracker.html', form=ExpenseForm(), transactions=transactions, insight=insight, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)

        worksheet = spreadsheet.worksheet(SHEET_NAMES['expense_tracker'])
        all_data = worksheet.get_all_records()
        transactions = [t for t in all_data if t['Email'] == form.email.data] if form.email.data else transactions
        transactions = calculate_running_balance(transactions)
        insight = generate_insight(transactions, language)
        return render_template('expense_tracker.html', form=form, transactions=transactions, insight=insight, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)
    except Exception as e:
        logger.error(f"Error in expense_tracker route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/expense_submit', methods=['POST'])
def expense_submit():
    form = ExpenseForm()
    language = session.get('language', 'English')
    if form.validate_on_submit():
        try:
            amount = float(re.sub(r'[,]', '', form.amount.data))
            if amount < 0:
                flash(translations[language]['Invalid Number'], 'error')
                return redirect(url_for('expense_tracker'))
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return redirect(url_for('expense_tracker'))

        transactions = session.get('transactions', [])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        transaction = {
            'Timestamp': timestamp,
            'FirstName': form.first_name.data,
            'Email': form.email.data,
            'Language': form.language.data,
            'Amount': str(amount),
            'Description': form.description.data,
            'Category': form.category.data,
            'TransactionType': form.transaction_type.data,
            'RunningBalance': '0'
        }
        transactions.append(transaction)
        transactions = calculate_running_balance(transactions)
        session['transactions'] = transactions

        save_to_google_sheets('expense_tracker', transaction)
        flash(translations[language]['Transaction Added'], 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'error')
    return redirect(url_for('expense_tracker'))

@app.route('/expense_edit/<int:id>', methods=['GET', 'POST'])
def expense_edit(id):
    form = ExpenseForm()
    language = session.get('language', 'English')
    transactions = session.get('transactions', [])
    
    if id < 0 or id >= len(transactions):
        flash(translations[language]['Invalid Transaction'], 'error')
        return redirect(url_for('expense_tracker'))

    if request.method == 'POST' and form.validate_on_submit():
        try:
            amount = float(re.sub(r'[,]', '', form.amount.data))
            if amount < 0:
                flash(translations[language]['Invalid Number'], 'error')
                return render_template('expense_tracker.html', form=form, transactions=transactions, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return render_template('expense_tracker.html', form=form, transactions=transactions, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)

        transactions[id].update({
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'FirstName': form.first_name.data,
            'Email': form.email.data,
            'Language': form.language.data,
            'Amount': str(amount),
            'Description': form.description.data,
            'Category': form.category.data,
            'TransactionType': form.transaction_type.data
        })
        transactions = calculate_running_balance(transactions)
        session['transactions'] = transactions

        save_to_google_sheets('expense_tracker', transactions[id])
        flash(translations[language]['Transaction Updated'], 'success')
        return redirect(url_for('expense_tracker'))
    
    form.first_name.data = transactions[id]['FirstName']
    form.email.data = transactions[id]['Email']
    form.language.data = transactions[id]['Language']
    form.amount.data = transactions[id]['Amount']
    form.description.data = transactions[id]['Description']
    form.category.data = transactions[id]['Category']
    form.transaction_type.data = transactions[id]['TransactionType']
    return render_template('expense_tracker.html', form=form, transactions=transactions, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL, WAITLIST_FORM_URL=WAITLIST_FORM_URL)

@app.route('/bill_planner', methods=['GET', 'POST'])
def bill_planner():
    form = BillForm()
    language = session.get('language', 'English')
    if language not in translations:
        language = 'English'
        session['language'] = language

    try:
        if request.method == 'POST' and form.validate_on_submit():
            due_date = parse_natural_date(form.due_date.data)
            if not due_date:
                flash(translations[language]['Enter a valid date'], 'error')
                return render_template('bill_planner.html', form=form, tasks=[], translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

            try:
                amount = float(re.sub(r'[,]', '', form.amount.data)) if form.amount.data else 0
                if amount < 0:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('bill_planner.html', form=form, tasks=[], translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
            except ValueError:
                flash(translations[language]['Invalid Number'], 'error')
                return render_template('bill_planner.html', form=form, tasks=[], translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            task = {
                'Timestamp': timestamp,
                'FirstName': form.first_name.data,
                'Email': form.email.data,
                'Language': form.language.data,
                'Description': form.description.data,
                'Amount': str(amount),
                'DueDate': due_date,
                'Category': form.category.data,
                'Recurrence': form.recurrence.data,
                'Status': 'Pending'
            }
            save_to_google_sheets('bill_planner', task)
            flash(translations[language]['Task Added'], 'success')
            return redirect(url_for('bill_planner'))

        worksheet = spreadsheet.worksheet(SHEET_NAMES['bill_planner'])
        all_data = worksheet.get_all_records()
        tasks = [t for t in all_data if t['Email'] == form.email.data] if form.email.data else all_data
        for task in tasks:
            try:
                due_date = datetime.strptime(task['DueDate'], '%Y-%m-%d')
                if task['Status'] == 'Pending' and due_date < datetime.now():
                    task['Status'] = 'Overdue'
            except ValueError:
                task['Status'] = 'Pending'
        return render_template('bill_planner.html', form=form, tasks=tasks, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
    except Exception as e:
        logger.error(f"Error in bill_planner route: {str(e)}\n{traceback.format_exc()}")
        raise

@app.route('/bill_submit', methods=['POST'])
def bill_submit():
    form = BillForm()
    language = session.get('language', 'English')
    if form.validate_on_submit():
        due_date = parse_natural_date(form.due_date.data)
        if not due_date:
            flash(translations[language]['Enter a valid date'], 'error')
            return redirect(url_for('bill_planner'))

        try:
            amount = float(re.sub(r'[,]', '', form.amount.data)) if form.amount.data else 0
            if amount < 0:
                flash(translations[language]['Invalid Number'], 'error')
                return redirect(url_for('bill_planner'))
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return redirect(url_for('bill_planner'))

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        task = {
            'Timestamp': timestamp,
            'FirstName': form.first_name.data,
            'Email': form.email.data,
            'Language': form.language.data,
            'Description': form.description.data,
            'Amount': str(amount),
            'DueDate': due_date,
            'Category': form.category.data,
            'Recurrence': form.recurrence.data,
            'Status': 'Pending'
        }
        save_to_google_sheets('bill_planner', task)
        flash(translations[language]['Task Added'], 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'error')
    return redirect(url_for('bill_planner'))

@app.route('/bill_edit/<int:id>', methods=['GET', 'POST'])
def bill_edit(id):
    form = BillForm()
    language = session.get('language', 'English')
    worksheet = spreadsheet.worksheet(SHEET_NAMES['bill_planner'])
    all_data = worksheet.get_all_records()
    
    if id < 0 or id >= len(all_data):
        flash(translations[language]['Invalid Task'], 'error')
        return redirect(url_for('bill_planner'))

    task = all_data[id]
    if request.method == 'POST' and form.validate_on_submit():
        due_date = parse_natural_date(form.due_date.data)
        if not due_date:
            flash(translations[language]['Enter a valid date'], 'error')
            return render_template('bill_planner.html', form=form, tasks=all_data, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        try:
            amount = float(re.sub(r'[,]', '', form.amount.data)) if form.amount.data else 0
            if amount < 0:
                flash(translations[language]['Invalid Number'], 'error')
                return render_template('bill_planner.html', form=form, tasks=all_data, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return render_template('bill_planner.html', form=form, tasks=all_data, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

        updated_task = {
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'FirstName': form.first_name.data,
            'Email': form.email.data,
            'Language': form.language.data,
            'Description': form.description.data,
            'Amount': str(amount),
            'DueDate': due_date,
            'Category': form.category.data,
            'Recurrence': form.recurrence.data,
            'Status': task['Status']
        }
        worksheet.update_row(id + 2, list(updated_task.values()))
        flash(translations[language]['Task Updated'], 'success')
        return redirect(url_for('bill_planner'))

    form.first_name.data = task['FirstName']
    form.email.data = task['Email']
    form.language.data = task['Language']
    form.description.data = task['Description']
    form.amount.data = task['Amount']
    form.due_date.data = task['DueDate']
    form.category.data = task['Category']
    form.recurrence.data = task['Recurrence']
    return render_template('bill_planner.html', form=form, tasks=all_data, translations=translations, language=language, FEEDBACK_FORM_URL=FEEDBACK_FORM_URL)

@app.route('/bill_complete/<int:id>', methods=['GET'])
def bill_complete(id):
    language = session.get('language', 'English')
    worksheet = spreadsheet.worksheet(SHEET_NAMES['bill_planner'])
    all_data = worksheet.get_all_records()
    
    if id < 0 or id >= len(all_data):
        flash(translations[language]['Invalid Task'], 'error')
        return redirect(url_for('bill_planner'))

    task = all_data[id]
    task['Status'] = 'Completed'
    task['Timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    worksheet.update_row(id + 2, list(task.values()))
    flash(translations[language]['Task Completed'], 'success')
    return redirect(url_for('bill_planner'))

if __name__ == '__main__':
    app.run(debug=True)
