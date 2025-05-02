from flask import Flask, render_template, request, redirect, url_for, flash, session
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
from datetime import datetime
from translations import translations
import pandas as pd

app = Flask(__name__, template_folder='ficore_templates', static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for Google Sheets and external URLs
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I"
FEEDBACK_FORM_URL = "https://forms.gle/NkiLicSykLyMnhJk7"
WAITLIST_FORM_URL = "https://forms.gle/3kXnJuDatTm8bT3x7"
CONSULTANCY_FORM_URL = "https://forms.gle/rfHhpD71MjLpET2K9"
INVESTING_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
SAVINGS_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
DEBT_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"
RECOVERY_COURSE_URL = "https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI"

# Sheet names for each feature
SHEET_NAMES = {
    'index': 'IndexSheet',
    'net_worth': 'NetWorthSheet',
    'emergency_fund': 'EmergencyFundSheet',
    'quiz': 'QuizSheet',
    'budget': 'BudgetSheet'
}

# Predefined headers for each feature
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
    ]
}

# Email configuration
EMAIL_ADDRESS = os.getenv('SMTP_USER')
EMAIL_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# Google Sheets setup
try:
    # Load credentials from environment variable
    credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if not credentials_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON environment variable not set")

    # Parse the JSON string into a dictionary
    try:
        credentials_dict = json.loads(credentials_json)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse GOOGLE_CREDENTIALS_JSON: {str(e)}")

    # Create credentials from the dictionary
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
    except Exception as e:
        raise Exception(f"Failed to create credentials: {str(e)}")

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    logger.info("Successfully connected to Google Sheets database")
except Exception as e:
    logger.error(f"Failed to connect to Google Sheets: {str(e)}")
    raise Exception("Database connection failed")

# Ensure all sheets exist with predefined headers
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
class SubmissionForm:
    def __init__(self):
        self.business_name = ''
        self.income_revenue = ''
        self.expenses_costs = ''
        self.debt_loan = ''
        self.debt_interest_rate = ''
        self.auto_email = ''
        self.phone_number = ''
        self.first_name = ''
        self.last_name = ''
        self.user_type = 'Business'
        self.email = ''
        self.language = 'English'

class NetWorthForm:
    def __init__(self):
        self.first_name = ''
        self.email = ''
        self.language = 'English'
        self.assets = 0
        self.liabilities = 0

class EmergencyFundForm:
    def __init__(self):
        self.first_name = ''
        self.email = ''
        self.language = 'English'
        self.monthly_expenses = 0

class QuizForm:
    def __init__(self):
        self.first_name = ''
        self.email = ''
        self.language = 'English'
        self.q1 = None
        self.q2 = None
        self.q3 = None
        self.q4 = None
        self.q5 = None

class BudgetForm:
    def __init__(self):
        self.first_name = ''
        self.email = ''
        self.auto_email = ''
        self.language = 'English'
        self.monthly_income = 0
        self.housing_expenses = 0
        self.food_expenses = 0
        self.transport_expenses = 0
        self.other_expenses = 0

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
        return badges
    user_row = user_df.iloc[0]
    if len(user_df) == 1:
        badges.append(translations[language]['First Health Score Completed!'])
    if user_row['HealthScore'] >= 50:
        badges.append(translations[language]['Financial Stability Achieved!'])
    if user_row['DebtToIncomeRatio'] < 0.3:
        badges.append(translations[language]['Debt Slayer!'])
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
        return translations[language]['Positive Value Advice']
    elif value == 0:
        return translations[language]['Zero Value Advice']
    else:
        return translations[language]['Negative Value Advice']

def get_badges(value, language):
    badges = []
    if value > 1000:
        badges.append(translations[language]['High Value Badge'])
    if value > 0:
        badges.append(translations[language]['Positive Value Badge'])
    return badges

def get_tips(language):
    return [
        translations[language]['Tip 1'],
        translations[language]['Tip 2'],
        translations[language]['Tip 3']
    ]

def get_courses(language):
    return [
        {'title': translations[language]['Course 1 Title'], 'link': INVESTING_COURSE_URL},
        {'title': translations[language]['Course 2 Title'], 'link': SAVINGS_COURSE_URL}
    ]

# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    form = SubmissionForm()
    language = session.get('language', 'English')
    if language not in translations:
        language = 'English'
        session['language'] = language
    if request.method == 'POST':
        form.business_name = request.form.get('business_name', '').strip()
        form.income_revenue = request.form.get('income_revenue', '').strip()
        form.expenses_costs = request.form.get('expenses_costs', '').strip()
        form.debt_loan = request.form.get('debt_loan', '').strip()
        form.debt_interest_rate = request.form.get('debt_interest_rate', '').strip()
        form.auto_email = request.form.get('auto_email', '').strip()
        form.phone_number = request.form.get('phone_number', '').strip()
        form.first_name = request.form.get('first_name', '').strip()
        form.last_name = request.form.get('last_name', '').strip()
        form.user_type = request.form.get('user_type', 'Business')
        form.email = request.form.get('email', '').strip()
        form.language = request.form.get('language', 'English')

        if not all([form.first_name, form.business_name, form.income_revenue, form.expenses_costs, form.debt_loan, form.debt_interest_rate, form.email, form.auto_email]):
            flash(translations[language]['First Name Required'] if not form.first_name else translations[language]['Business Name Required'] if not form.business_name else translations[language]['Invalid Number'], 'error')
            return render_template('index.html', form=form, translations=translations[language])

        if form.email != form.auto_email:
            flash(translations[language]['Emails Do Not Match'], 'error')
            return render_template('index.html', form=form, translations=translations[language])

        try:
            for field in ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate']:
                value = float(re.sub(r'[,]', '', getattr(form, field)))
                if value < 0:
                    flash(translations[language]['Invalid Number'], 'error')
                    return render_template('index.html', form=form, translations=translations[language])
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return render_template('index.html', form=form, translations=translations[language])

        return redirect(url_for('submit'))
    return render_template('index.html', form=form, translations=translations[language])

@app.route('/submit', methods=['POST'])
def submit():
    form = SubmissionForm()
    language = session.get('language', 'English')
    if language not in translations:
        language = 'English'
        session['language'] = language

    try:
        form.business_name = request.form.get('business_name', '').strip()
        form.income_revenue = request.form.get('income_revenue', '').strip()
        form.expenses_costs = request.form.get('expenses_costs', '').strip()
        form.debt_loan = request.form.get('debt_loan', '').strip()
        form.debt_interest_rate = request.form.get('debt_interest_rate', '').strip()
        form.auto_email = request.form.get('auto_email', '').strip()
        form.phone_number = request.form.get('phone_number', '').strip()
        form.first_name = request.form.get('first_name', '').strip()
        form.last_name = request.form.get('last_name', '').strip()
        form.user_type = request.form.get('user_type', 'Business')
        form.email = request.form.get('email', '').strip()
        form.language = request.form.get('language', 'English')

        if not all([form.first_name, form.business_name, form.income_revenue, form.expenses_costs, form.debt_loan, form.debt_interest_rate, form.email, form.auto_email]):
            flash(translations[language]['First Name Required'] if not form.first_name else translations[language]['Business Name Required'] if not form.business_name else translations[language]['Invalid Number'], 'error')
            return redirect(url_for('home', language=language))

        if form.email != form.auto_email:
            flash(translations[language]['Emails Do Not Match'], 'error')
            return redirect(url_for('home', language=language))

        try:
            income_revenue = float(re.sub(r'[,]', '', form.income_revenue))
            expenses_costs = float(re.sub(r'[,]', '', form.expenses_costs))
            debt_loan = float(re.sub(r'[,]', '', form.debt_loan))
            debt_interest_rate = float(re.sub(r'[,]', '', form.debt_interest_rate))
            if any(v < 0 for v in [income_revenue, expenses_costs, debt_loan, debt_interest_rate]):
                flash(translations[language]['Invalid Number'], 'error')
                return redirect(url_for('home', language=language))
        except ValueError:
            flash(translations[language]['Invalid Number'], 'error')
            return redirect(url_for('home', language=language))

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            timestamp, form.business_name, form.income_revenue, form.expenses_costs, form.debt_loan,
            form.debt_interest_rate, form.auto_email, form.phone_number, form.first_name, form.last_name,
            form.user_type, form.email, '', form.language, ''
        ]
        save_to_google_sheets('index', data)

        worksheet = spreadsheet.worksheet(SHEET_NAMES['index'])
        all_data = worksheet.get_all_records()
        df = calculate_health_score(pd.DataFrame(all_data))
        user_df = df[df['Email'] == form.email].copy()
        if user_df.empty:
            user_df = pd.DataFrame([data], columns=PREDETERMINED_HEADERS['index'])
            user_df = calculate_health_score(user_df)
        all_users_df = df.copy()

        badges = assign_badges(user_df, all_users_df, language)
        user_df.at[user_df.index[0], 'Badges'] = ','.join(badges)
        worksheet.update_cell(len(all_data) + 2, 13, ','.join(badges))  # Update Badges column

        all_users_df = all_users_df.sort_values('HealthScore', ascending=False).reset_index(drop=True)
        user_index = all_users_df.index[all_users_df['Email'] == form.email].tolist()[0]
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
            user_name=form.first_name,
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
        if send_email(form.email, translations[language]['Score Report Subject'].format(user_name=form.first_name), email_body, language):
            flash(translations[language]['Email sent successfully'], 'success')
        else:
            flash(translations[language]['Failed to send email'], 'error')

        session['language'] = form.language
        session['full_name'] = form.first_name

        flash(translations[language]['Submission Success'], 'success')
        return render_template(
            'dashboard.html',
            first_name=form.first_name,
            last_name=form.last_name or '',
            email=form.email,
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
            translations=translations[language]
        )
    except Exception as e:
        logger.error(f"Error processing submission: {str(e)}")
        flash(translations[language]['Error processing form'], 'error')
        return redirect(url_for('home', language=language))

@app.route('/net_worth', methods=['GET', 'POST'])
def net_worth():
    form = NetWorthForm()
    if request.method == 'POST':
        try:
            form.first_name = request.form.get('first_name', '').strip()
            form.email = request.form.get('email', '').strip()
            form.language = request.form.get('language', 'English')
            assets_str = request.form.get('assets', '0').replace(',', '')
            liabilities_str = request.form.get('liabilities', '0').replace(',', '')

            if not form.first_name:
                flash(translations[form.language]['First Name Required'], 'error')
                return render_template('net_worth_form.html', form=form, translations=translations[form.language])

            try:
                form.assets = float(assets_str)
                form.liabilities = float(liabilities_str)
            except ValueError:
                flash(translations[form.language]['Invalid Number'], 'error')
                return render_template('net_worth_form.html', form=form, translations=translations[form.language])

            net_worth = form.assets - form.liabilities
            rank = get_rank_from_db('net_worth', net_worth, 'NetWorth')
            advice = get_advice(net_worth, form.language)
            badges = get_badges(net_worth, form.language)
            tips = get_tips(form.language)
            courses = get_courses(form.language)

            chart_data = {'Assets': form.assets, 'Liabilities': form.liabilities}
            chart_html = generate_chart(chart_data, translations[form.language]['Asset-Liability Breakdown'])
            comparison_chart_html = generate_chart({'You': net_worth, 'Peers': net_worth * 0.9}, translations[form.language]['Comparison to Peers'])

            if not chart_html or not comparison_chart_html:
                flash(translations[form.language]['Chart Unavailable'], 'error')
                return render_template('net_worth_form.html', form=form, translations=translations[form.language])

            data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'FirstName': form.first_name,
                'Email': form.email,
                'Language': form.language,
                'Assets': form.assets,
                'Liabilities': form.liabilities,
                'NetWorth': net_worth
            }
            save_to_google_sheets('net_worth', data)

            email_body = translations[form.language]['Email Body'].format(
                user_name=form.first_name,
                health_score=net_worth,
                score_description=advice,
                rank=rank,
                total_users=100,
                course_url=courses[0]['link'],
                course_title=courses[0]['title'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body, form.language):
                flash(translations[form.language]['Email sent successfully'], 'success')
            else:
                flash(translations[form.language]['Failed to send email'], 'error')

            session['language'] = form.language
            session['full_name'] = form.first_name

            flash(translations[form.language]['Submission Success'], 'success')
            return render_template('net_worth_dashboard.html', net_worth=net_worth, rank=rank, advice=advice, badges=badges, tips=tips, courses=courses, chart_html=chart_html, comparison_chart_html=comparison_chart_html, full_name=form.first_name, translations=translations[form.language])
        except Exception as e:
            logger.error(f"Error in net_worth route: {str(e)}")
            flash(translations[form.language]['Error processing form'], 'error')
            return render_template('net_worth_form.html', form=form, translations=translations[form.language])
    return render_template('net_worth_form.html', form=form, translations=translations.get(session.get('language', 'English'), translations['English']))

@app.route('/emergency_fund', methods=['GET', 'POST'])
def emergency_fund():
    form = EmergencyFundForm()
    if request.method == 'POST':
        try:
            form.first_name = request.form.get('first_name', '').strip()
            form.email = request.form.get('email', '').strip()
            form.language = request.form.get('language', 'English')
            monthly_expenses_str = request.form.get('monthly_expenses', '0').replace(',', '')

            if not form.first_name:
                flash(translations[form.language]['First Name Required'], 'error')
                return render_template('emergency_fund_form.html', form=form, translations=translations[form.language])

            try:
                form.monthly_expenses = float(monthly_expenses_str)
            except ValueError:
                flash(translations[form.language]['Invalid Number'], 'error')
                return render_template('emergency_fund_form.html', form=form, translations=translations[form.language])

            emergency_fund = form.monthly_expenses * 3
            rank = get_rank_from_db('emergency_fund', emergency_fund, 'EmergencyFund')
            advice = get_advice(emergency_fund, form.language)
            badges = get_badges(emergency_fund, form.language)
            tips = get_tips(form.language)
            courses = get_courses(form.language)

            chart_data = {'Monthly Expenses': form.monthly_expenses, 'Emergency Fund': emergency_fund}
            chart_html = generate_chart(chart_data, translations[form.language]['Expense-Fund Breakdown'])
            comparison_chart_html = generate_chart({'You': emergency_fund, 'Peers': emergency_fund * 0.9}, translations[form.language]['Comparison to Peers'])

            if not chart_html or not comparison_chart_html:
                flash(translations[form.language]['Chart Unavailable'], 'error')
                return render_template('emergency_fund_form.html', form=form, translations=translations[form.language])

            data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'FirstName': form.first_name,
                'Email': form.email,
                'Language': form.language,
                'MonthlyExpenses': form.monthly_expenses,
                'EmergencyFund': emergency_fund
            }
            save_to_google_sheets('emergency_fund', data)

            email_body = translations[form.language]['Email Body'].format(
                user_name=form.first_name,
                health_score=emergency_fund,
                score_description=advice,
                rank=rank,
                total_users=100,
                course_url=courses[0]['link'],
                course_title=courses[0]['title'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body, form.language):
                flash(translations[form.language]['Email sent successfully'], 'success')
            else:
                flash(translations[form.language]['Failed to send email'], 'error')

            session['language'] = form.language
            session['full_name'] = form.first_name

            flash(translations[form.language]['Submission Success'], 'success')
            return render_template('emergency_fund_dashboard.html', emergency_fund=emergency_fund, rank=rank, advice=advice, badges=badges, tips=tips, courses=courses, chart_html=chart_html, comparison_chart_html=comparison_chart_html, full_name=form.first_name, translations=translations[form.language])
        except Exception as e:
            logger.error(f"Error in emergency_fund route: {str(e)}")
            flash(translations[form.language]['Error processing form'], 'error')
            return render_template('emergency_fund_form.html', form=form, translations=translations[form.language])
    return render_template('emergency_fund_form.html', form=form, translations=translations.get(session.get('language', 'English'), translations['English']))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    form = QuizForm()
    if request.method == 'POST':
        try:
            form.first_name = request.form.get('first_name', '').strip()
            form.email = request.form.get('email', '').strip()
            form.language = request.form.get('language', 'English')
            form.q1 = request.form.get('q1')
            form.q2 = request.form.get('q2')
            form.q3 = request.form.get('q3')
            form.q4 = request.form.get('q4')
            form.q5 = request.form.get('q5')

            if not form.first_name:
                flash(translations[form.language]['First Name Required'], 'error')
                return render_template('quiz_form.html', form=form, translations=translations[form.language])

            answers = [form.q1, form.q2, form.q3, form.q4, form.q5]
            if None in answers:
                flash(translations[form.language]['Please answer all questions before submitting!'], 'error')
                return render_template('quiz_form.html', form=form, translations=translations[form.language])

            score = sum(1 for q in answers if q == '1') * 20
            rank = get_rank_from_db('quiz', score, 'QuizScore')
            advice = get_advice(score, form.language)
            badges = get_badges(score, form.language)
            tips = get_tips(form.language)
            courses = get_courses(form.language)

            chart_data = {'Q1': int(form.q1 == '1') * 20, 'Q2': int(form.q2 == '1') * 20, 'Q3': int(form.q3 == '1') * 20, 'Q4': int(form.q4 == '1') * 20, 'Q5': int(form.q5 == '1') * 20}
            chart_html = generate_chart(chart_data, translations[form.language]['Question Performance'])
            comparison_chart_html = generate_chart({'You': score, 'Peers': score * 0.9}, translations[form.language]['Comparison to Peers'])

            if not chart_html or not comparison_chart_html:
                flash(translations[form.language]['Chart Unavailable'], 'error')
                return render_template('quiz_form.html', form=form, translations=translations[form.language])

            data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'FirstName': form.first_name,
                'Email': form.email,
                'Language': form.language,
                'Q1': form.q1,
                'Q2': form.q2,
                'Q3': form.q3,
                'Q4': form.q4,
                'Q5': form.q5,
                'QuizScore': score
            }
            save_to_google_sheets('quiz', data)

            email_body = translations[form.language]['Email Body'].format(
                user_name=form.first_name,
                health_score=score,
                score_description=advice,
                rank=rank,
                total_users=100,
                course_url=courses[0]['link'],
                course_title=courses[0]['title'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body, form.language):
                flash(translations[form.language]['Email sent successfully'], 'success')
            else:
                flash(translations[form.language]['Failed to send email'], 'error')

            session['language'] = form.language
            session['full_name'] = form.first_name

            flash(translations[form.language]['Submission Success'], 'success')
            return render_template('quiz_dashboard.html', score=score, rank=rank, advice=advice, badges=badges, tips=tips, courses=courses, chart_html=chart_html, comparison_chart_html=comparison_chart_html, full_name=form.first_name, translations=translations[form.language])
        except Exception as e:
            logger.error(f"Error in quiz route: {str(e)}")
            flash(translations[form.language]['Error processing form'], 'error')
            return render_template('quiz_form.html', form=form, translations=translations[form.language])
    return render_template('quiz_form.html', form=form, translations=translations.get(session.get('language', 'English'), translations['English']))

@app.route('/budget', methods=['GET', 'POST'])
def budget():
    form = BudgetForm()
    if request.method == 'POST':
        try:
            form.first_name = request.form.get('first_name', '').strip()
            form.email = request.form.get('email', '').strip()
            form.auto_email = request.form.get('auto_email', '').strip()
            form.language = request.form.get('language', 'English')
            monthly_income_str = request.form.get('monthly_income', '0').replace(',', '')
            housing_expenses_str = request.form.get('housing_expenses', '0').replace(',', '')
            food_expenses_str = request.form.get('food_expenses', '0').replace(',', '')
            transport_expenses_str = request.form.get('transport_expenses', '0').replace(',', '')
            other_expenses_str = request.form.get('other_expenses', '0').replace(',', '')

            if not form.first_name:
                flash(translations[form.language]['First Name Required'], 'error')
                return render_template('budget_form.html', form=form, translations=translations[form.language])

            if form.email != form.auto_email:
                flash(translations[form.language]['Emails Do Not Match'], 'error')
                return render_template('budget_form.html', form=form, translations=translations[form.language])

            try:
                form.monthly_income = float(monthly_income_str)
                form.housing_expenses = float(housing_expenses_str)
                form.food_expenses = float(food_expenses_str)
                form.transport_expenses = float(transport_expenses_str)
                form.other_expenses = float(other_expenses_str)
            except ValueError:
                flash(translations[form.language]['Invalid Number'], 'error')
                return render_template('budget_form.html', form=form, translations=translations[form.language])

            total_expenses = form.housing_expenses + form.food_expenses + form.transport_expenses + form.other_expenses
            surplus_deficit = form.monthly_income - total_expenses
            rank = get_rank_from_db('budget', surplus_deficit, 'SurplusDeficit')
            advice = get_advice(surplus_deficit, form.language)
            badges = get_badges(surplus_deficit, form.language)
            tips = get_tips(form.language)
            courses = get_courses(form.language)

            chart_data = {
                'Housing': form.housing_expenses,
                'Food': form.food_expenses,
                'Transport': form.transport_expenses,
                'Other': form.other_expenses
            }
            chart_html = generate_chart(chart_data, translations[form.language]['Expense Breakdown'])
            comparison_chart_html = generate_chart({'You': surplus_deficit, 'Peers': surplus_deficit * 0.9}, translations[form.language]['Comparison to Peers'])

            if not chart_html or not comparison_chart_html:
                flash(translations[form.language]['Chart Unavailable'], 'error')
                return render_template('budget_form.html', form=form, translations=translations[form.language])

            data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'FirstName': form.first_name,
                'Email': form.email,
                'AutoEmail': form.auto_email,
                'Language': form.language,
                'MonthlyIncome': form.monthly_income,
                'HousingExpenses': form.housing_expenses,
                'FoodExpenses': form.food_expenses,
                'TransportExpenses': form.transport_expenses,
                'OtherExpenses': form.other_expenses,
                'TotalExpenses': total_expenses,
                'SurplusDeficit': surplus_deficit
            }
            save_to_google_sheets('budget', data)

            email_body = translations[form.language]['Email Body'].format(
                user_name=form.first_name,
                health_score=surplus_deficit,
                score_description=advice,
                rank=rank,
                total_users=100,
                course_url=courses[0]['link'],
                course_title=courses[0]['title'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body, form.language):
                flash(translations[form.language]['Email sent successfully'], 'success')
            else:
                flash(translations[form.language]['Failed to send email'], 'error')

            session['language'] = form.language
            session['full_name'] = form.first_name

            flash(translations[form.language]['Submission Success'], 'success')
            return render_template('budget_dashboard.html', monthly_income=form.monthly_income, total_expenses=total_expenses, surplus_deficit=surplus_deficit, rank=rank, advice=advice, badges=badges, tips=tips, courses=courses, chart_html=chart_html, comparison_chart_html=comparison_chart_html, full_name=form.first_name, translations=translations[form.language])
        except Exception as e:
            logger.error(f"Error in budget route: {str(e)}")
            flash(translations[form.language]['Error processing form'], 'error')
            return render_template('budget_form.html', form=form, translations=translations[form.language])
    return render_template('budget_form.html', form=form, translations=translations.get(session.get('language', 'English'), translations['English']))

if __name__ == '__main__':
    app.run(debug=True)
