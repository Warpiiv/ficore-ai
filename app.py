from flask import Flask, render_template, request, flash, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
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
from translations import translations  # Importing translations from separate file

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
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPES)
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
            # Set headers if sheet is empty or headers don't match
            current_headers = worksheet.row_values(1)
            if not current_headers or current_headers != PREDETERMINED_HEADERS[feature]:
                worksheet.clear()
                worksheet.append_row(PREDETERMINED_HEADERS[feature])
                logger.info(f"Set headers for {sheet_name}: {PREDETERMINED_HEADERS[feature]}")
    except Exception as e:
        logger.error(f"Error setting up sheets: {str(e)}")
        raise

# Run sheet setup on app startup
setup_sheets()

# Forms
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
def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

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

def get_advice(score_or_balance, language):
    try:
        if score_or_balance > 0:
            return translations[language]['Strong Financial Health']
        return translations[language]['Financial Strain']
    except Exception as e:
        logger.error(f"Error generating advice: {str(e)}")
        return translations[language].get('Error retrieving advice', 'Unable to generate advice at this time.')

def get_badges(score_or_balance, language):
    try:
        badges = []
        if score_or_balance > 0:
            badges.append(translations[language]['Financial Stability Achieved!'])
        if score_or_balance >= 100000:
            badges.append(translations[language]['Debt Slayer!'])
        return badges
    except Exception as e:
        logger.error(f"Error generating badges: {str(e)}")
        return []

def get_tips(language):
    return [
        translations[language]['Build Savings'],
        translations[language]['Cut Costs'],
        translations[language]['Reduce Debt']
    ]

def get_courses(language):
    return [
        {"title": translations[language]['Recommended Course'], "link": SAVINGS_COURSE_URL},
        {"title": translations[language]['Recommended Course'], "link": DEBT_COURSE_URL}
    ]

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

# Routes
@app.route('/')
def landing():
    language = session.get('language', 'English')
    if language not in translations:
        language = 'English'
        session['language'] = language
    return render_template('index.html', translations=translations[language])

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
                total_users=100,  # Mock total users
                course_url=courses[0]['link'],
                course_title=courses[0]['title'],
                FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
                WAITLIST_FORM_URL=WAITLIST_FORM_URL,
                CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
            )
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body):
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
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body):
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
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body):
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
            if send_email(form.email, translations[form.language]['Score Report Subject'].format(user_name=form.first_name), email_body):
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
