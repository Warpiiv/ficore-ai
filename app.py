from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, send_from_directory
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
import traceback

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

# Translation dictionary
translations = {
    'English': {
        'Welcome': 'Welcome',
        'Email': 'Email',
        'Your Financial Health Summary': 'Your Financial Health Summary',
        'Your Financial Health Score': 'Your Financial Health Score',
        'Ranked': 'Ranked',
        'out of': 'out of',
        'users': 'users',
        'Strong Financial Health': 'Your score indicates strong financial health. Focus on investing surplus funds to grow your wealth.',
        'Stable Finances': 'Your finances are stable but could improve. Consider saving more or reducing expenses.',
        'Financial Strain': 'Your score suggests financial strain. Prioritize paying off debt and managing expenses.',
        'Urgent Attention Needed': 'Your finances need urgent attention. Seek professional advice and explore recovery strategies.',
        'Score Breakdown': 'Score Breakdown',
        'Chart Unavailable': 'Chart unavailable at this time.',
        'Score Composition': 'Your score is composed of three components',
        'Cash Flow': 'Cash Flow',
        'Cash Flow Description': 'Reflects how much income remains after expenses. Higher values indicate better financial flexibility.',
        'Debt-to-Income Ratio': 'Debt-to-Income Ratio',
        'Debt-to-Income Description': 'Measures debt relative to income. Lower ratios suggest manageable debt levels.',
        'Debt Interest Burden': 'Debt Interest Burden',
        'Debt Interest Description': 'Indicates the impact of interest rates on your finances. Lower burdens mean less strain from debt.',
        'Balanced Components': 'Your components show balanced financial health. Maintain strong cash flow and low debt.',
        'Components Need Attention': 'One or more components may need attention. Focus on improving cash flow or reducing debt.',
        'Components Indicate Challenges': 'Your components indicate challenges. Work on increasing income, cutting expenses, or lowering debt interest.',
        'Your Badges': 'Your Badges',
        'No Badges Yet': 'No badges earned yet. Keep submitting to earn more!',
        'Recommended Learning': 'Recommended Learning',
        'Recommended Course': 'Recommended Course',
        'Enroll in': 'Enroll in',
        'Enroll Now': 'Enroll Now',
        'Quick Financial Tips': 'Quick Financial Tips',
        'Invest': 'Invest',
        'Invest Wisely': 'Allocate surplus cash to low-risk investments like treasury bonds to grow wealth.',
        'Scale': 'Scale',
        'Scale Smart': 'Reinvest profits into your business to expand operations sustainably.',
        'Build': 'Build',
        'Build Savings': 'Save 10% of your income monthly to create an emergency fund.',
        'Cut': 'Cut',
        'Cut Costs': 'Review expenses and reduce non-essential spending to boost cash flow.',
        'Reduce': 'Reduce',
        'Reduce Debt': 'Prioritize paying off high-interest loans to ease financial strain.',
        'Boost': 'Boost',
        'Boost Income': 'Explore side hustles or new revenue streams to improve cash flow.',
        'How You Compare': 'How You Compare to Others',
        'Your Rank': 'Your rank of',
        'places you': 'places you',
        'Top 10%': 'in the top 10% of users, indicating exceptional financial health compared to peers.',
        'Top 30%': 'in the top 30%, showing above-average financial stability.',
        'Middle Range': 'in the middle range, suggesting room for improvement to climb the ranks.',
        'Lower Range': 'in the lower range, highlighting the need for strategic financial planning.',
        'Regular Submissions': 'Regular submissions can help track your progress and improve your standing.',
        'Whats Next': 'What’s Next? Unlock Further Insights',
        'Back to Home': 'Back to Home',
        'Provide Feedback': 'Provide Feedback',
        'Join Waitlist': 'Join Premium Waitlist',
        'Book Consultancy': 'Book Consultancy',
        'Contact Us': 'Contact us at',
        'for support': 'for support',
        'Ficore AI Financial Health Score': 'Ficore AI Financial Health Score',
        'Get Your Score': 'Get your financial health score and personalized insights instantly!',
        'Personal Information': 'Personal Information',
        'Enter your first name': 'Enter your first name',
        'First Name Required': 'First name is required.',
        'Enter your last name (optional)': 'Enter your last name (optional)',
        'Enter your email': 'Enter your email',
        'Invalid Email': 'Please enter a valid email address.',
        'Confirm your email': 'Confirm your email',
        'Enter phone number (optional)': 'Enter phone number (optional)',
        'Language': 'Language',
        'Business Information': 'Business Information',
        'Enter your business name': 'Enter your business name',
        'Business Name Required': 'Business name is required.',
        'User Type': 'User Type',
        'Financial Information': 'Financial Information',
        'Enter monthly income/revenue': 'Enter monthly income/revenue',
        'Enter monthly expenses/costs': 'Enter monthly expenses/costs',
        'Enter total debt/loan amount': 'Enter total debt/loan amount',
        'Enter debt interest rate (%)': 'Enter debt interest rate (%)',
        'Invalid Number': 'Please enter a valid number.',
        'Submit': 'Submit',
        'Top 10% Subject': '🔥 You\'re Top 10%! Your Ficore Score Report Awaits!',
        'Score Report Subject': '📊 Your Ficore Score Report is Ready, {user_name}!',
        'Email Body': '''
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
                <p style="margin-bottom: 10px;">
                    If you don’t see this email in your inbox, please check your spam or junk folder.
                </p>
                <style>
                    a:hover { background-color: #1B5E20 !important; }
                    a[href="{WAITLIST_FORM_URL}"]:hover { background-color: #0D47A1 !important; }
                    a[href="{course_url}"]:hover { background-color: #F9A825 !important; }
                </style>
                <p>Best regards,<br>The Ficore AI Team</p>
            </body>
            </html>
        ''',
        'First Health Score Completed!': 'First Health Score Completed!',
        'Financial Stability Achieved!': 'Financial Stability Achieved!',
        'Debt Slayer!': 'Debt Slayer!'
    },
    'Hausa': {
        'Welcome': 'Barka da zuwa',
        'Email': 'Imel',
        'Your Financial Health Summary': 'Takaitaccen Lafiyar Kuɗin Ku',
        'Your Financial Health Score': 'Makiyon Lafiyar Kuɗin Ku',
        'Ranked': 'An sanya daraja',
        'out of': 'daga cikin',
        'users': 'masu amfani',
        'Strong Financial Health': 'Makiyon ku yana nuna ƙarfin lafiyar kuɗi. Mai da hankali kan saka hannun jari a cikin kuɗin da ya rage don haɓaka dukiya.',
        'Stable Finances': 'Kuɗin ku suna da kwanciyar hankali amma suna iya inganta. Yi la’akari da adanawa ko rage kashe kuɗi.',
        'Financial Strain': 'Makiyon ku yana nuna damuwar kuɗi. Fifita biyan bashi da sarrafa kashe kuɗi.',
        'Urgent Attention Needed': 'Kuɗin ku suna buƙatar kulawa cikin gaggawa. Nemi shawarar ƙwararru kuma bincika dabarun farfadowa.',
        'Score Breakdown': 'Rarraba Makiyo',
        'Chart Unavailable': 'Chart ba ya samuwa a wannan lokacin.',
        'Score Composition': 'Makiyon ku ya ƙunshi abubuwa uku',
        'Cash Flow': 'Kwararar Kuɗi',
        'Cash Flow Description': 'Yana nuna adadin kuɗin shiga da ya rage bayan kashe kuɗi. Maɗaukakin ƙima yana nuna mafi kyawun sassaucin kuɗi.',
        'Debt-to-Income Ratio': 'Rabo na Bashi zuwa Kuɗin shiga',
        'Debt-to-Income Description': 'Yana auna bashi dangane da kuɗin shiga. Ƙananan rabon yana nuna matakan bashi mai sauƙi.',
        'Debt Interest Burden': 'Nauyin Riba na Bashi',
        'Debt Interest Description': 'Yana nuna tasirin ƙimar riba a kan kuɗin ku. Ƙananan nauyi yana nufin ƙarancin damuwa daga bashi.',
        'Balanced Components': 'Abubuwan da ke cikin ku suna nuna daidaitaccen lafiyar kuɗi. Ci gaba da kiyaye kwararar kuɗi mai ƙarfi da ƙarancin bashi.',
        'Components Need Attention': 'Ɗaya ko fiye da abubuwan da ke ciki na iya buƙatar kulawa. Mai da hankali kan inganta kwararar kuɗi ko rage bashi.',
        'Components Indicate Challenges': 'Abubuwan da ke cikin ku suna nuna ƙalubale. Yi aiki kan ƙara kuɗin shiga, yanke kashe kuɗi, ko rage ribar bashi.',
        'Your Badges': 'Bajojin Ku',
        'No Badges Yet': 'Ba a sami baji ba tukuna. Ci gaba da ƙaddamarwa don samun ƙari!',
        'Recommended Learning': 'Koyan da Aka Shawarta',
        'Recommended Course': 'Koyan da Aka Shawarta',
        'Enroll in': 'Shiga cikin',
        'Enroll Now': 'Shiga Yanzu',
        'Quick Financial Tips': 'Shawarwari na Kuɗi na Gaggawa',
        'Invest': 'Saka hannun jari',
        'Invest Wisely': 'Sanya kuɗin da ya rage a cikin saka hannun jari mai ƙarancin haɗari kamar takardun shaida don haɓaka dukiya.',
        'Scale': 'Faɗaɗa',
        'Scale Smart': 'Sake saka riba a cikin kasuwancin ku don faɗaɗa ayyuka cikin dorewa.',
        'Build': 'Gina',
        'Build Savings': 'Ajiye 10% na kuɗin shigarka kowane wata don ƙirƙirar asusun gaggawa.',
        'Cut': 'Yanke',
        'Cut Costs': 'Duba kashe kuɗi kuma rage kashe kuɗin da ba dole ba don haɓaka kwararar kuɗi.',
        'Reduce': 'Rage',
        'Reduce Debt': 'Fifita biyan lamuni masu ƙimar riba don sauƙaƙe damuwar kuɗi.',
        'Boost': 'Ƙarfafa',
        'Boost Income': 'Bincika ayyukan gefe ko sabbin hanyoyin samun kuɗin shiga don inganta kwararar kuɗi.',
        'How You Compare': 'Yadda Kuke Kwatanta da Wasu',
        'Your Rank': 'Matsayin ku na',
        'places you': 'ya sanya ku',
        'Top 10%': 'a cikin sama da 10% na masu amfani, yana nuna mafi kyawun lafiyar kuɗi idan aka kwatanta da takwarorinsu.',
        'Top 30%': 'a cikin sama da 30%, yana nuna kwanciyar hankali na kuɗi sama da matsakaici.',
        'Middle Range': 'a cikin kewayon tsakiya, yana nuna sarari don ingantawa don hawa matsayi.',
        'Lower Range': 'a cikin kewayon ƙasa, yana nuna buƙatar tsara kuɗi mai dabara.',
        'Regular Submissions': 'Ƙaddamarwa akai-akai na iya taimakawa wajen bin diddigin ci gaban ku da inganta matsayin ku.',
        'Whats Next': 'Me ke Gaba? Buɗe Ƙarin Fahimta',
        'Back to Home': 'Koma Gida',
        'Provide Feedback': 'Bayar da Shawara',
        'Join Waitlist': 'Shiga Jerin Jirage',
        'Book Consultancy': 'Yi Alƙawarin Shawara',
        'Contact Us': 'Tuntube mu a',
        'for support': 'don tallafi',
        'Ficore AI Financial Health Score': 'Makiyon Lafiyar Kuɗin Ficore AI',
        'Get Your Score': 'Sami makiyon lafiyar kuɗin ku da fahimta na keɓaɓɓu nan take!',
        'Personal Information': 'Bayanan Kai',
        'Enter your first name': 'Shigar da sunanka na farko',
        'First Name Required': 'Ana buƙatar sunan farko.',
        'Enter your last name (optional)': 'Shigar da sunanka na ƙarshe (na zaɓi)',
        'Enter your email': 'Shigar da imel ɗinka',
        'Invalid Email': 'Da fatan za a shigar da adireshin imel mai inganci.',
        'Confirm your email': 'Tabbatar da imel ɗinka',
        'Enter phone number (optional)': 'Shigar da lambar waya (na zaɓi)',
        'Language': 'Harshe',
        'Business Information': 'Bayanan Kasuwanci',
        'Enter your business name': 'Shigar da sunan kasuwancinka',
        'Business Name Required': 'Ana buƙatar sunan kasuwanci.',
        'User Type': 'Nau’in Mai Amfani',
        'Financial Information': 'Bayanan Kuɗi',
        'Enter monthly income/revenue': 'Shigar da kuɗin shiga/kudin shiga na wata-wata',
        'Enter monthly expenses/costs': 'Shigar da kashe kuɗi/kudin wata-wata',
        'Enter total debt/loan amount': 'Shigar da jimillar bashi/lamuni',
        'Enter debt interest rate (%)': 'Shigar da ƙimar ribar bashi (%)',
        'Invalid Number': 'Da fatan za a shigar da lamba mai inganci.',
        'Submit': 'Sallama',
        'Top 10% Subject': '🔥 Kuna cikin Sama da 10%! Rahoton Makiyon Ficore Yana Jiran Ku!',
        'Score Report Subject': '📊 Rahoton Makiyon Ficore Yana Shirye, {user_name}!',
        'Email Body': '''
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #FFFFFF; margin: 0;">Makiyon Lafiyar Kuɗin Ficore AI</h2>
                    <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Tikitin ci gaban kuɗi na Afirka
                    </p>
                </div>
                <p>Mai girma {user_name},</p>
                <p>Mun ƙididdige Makiyon Lafiyar Kuɗin Ficore AI bisa ƙaddamarwar ku na kwanan nan.</p>
                <ul>
                    <li><strong>Makiyo</strong>: {health_score}/100</li>
                    <li><strong>Shawara</strong>: {score_description}</li>
                    <li><strong>Matsayi</strong>: #{int(rank)} daga cikin {total_users} masu amfani</li>
                </ul>
                <p>Bi shawarar da ke sama don inganta lafiyar kuɗin ku. Muna nan don tallafa muku kowane mataki—ɗauki ƙaramin aiki a yau don ƙarfafa kuɗin ku don kasuwancinku, burinku, da makomarku!</p>
                <p style="margin-bottom: 10px;">
                    Kuna son ƙarin koyo? Duba wannan kwas: 
                    <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">{course_title}</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Da fatan za a ba da shawara kan kwarewarku: 
                    <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Fom ɗin Shawara</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kuna son Fahimta Mai Hankali? Shiga jerin jiran Ficore Premium: 
                    <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #1976D2; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Shiga Jerin Jirage</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kuna buƙatar shawara ta keɓaɓɓu? 
                    <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #388E3C; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Yi Alƙawarin Shawara</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Idan ba ku ga wannan imel a cikin akwatin saƙonninku ba, da fatan za a duba foldar spam ko junk ɗinku.
                </p>
                <style>
                    a:hover { background-color: #1B5E20 !important; }
                    a[href="{WAITLIST_FORM_URL}"]:hover { background-color: #0D47A1 !important; }
                    a[href="{course_url}"]:hover { background-color: #F9A825 !important; }
                </style>
                <p>Gaisuwa mafi kyau,<br>Ƙungiyar Ficore AI</p>
            </body>
            </html>
        ''',
        'First Health Score Completed!': 'Makiyon Lafiya na Farko An Kammala!',
        'Financial Stability Achieved!': 'An Sami Kwanciyar Hankali na Kuɗi!',
        'Debt Slayer!': 'Mai Kashe Bashi!'
    }
}

# Constants for Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:N'
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
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName', 'UserType', 'Email', 'Badges', 'Language'
]

# Flask-WTF form for submission
class SubmissionForm(FlaskForm):
    business_name = StringField('Business Name', validators=[DataRequired()])
    income_revenue = FloatField('Income Revenue', validators=[DataRequired()])
    expenses_costs = FloatField('Expenses Costs', validators=[DataRequired()])
    debt_loan = FloatField('Debt Loan', validators=[DataRequired()])
    debt_interest_rate = FloatField('Debt Interest Rate', validators=[DataRequired()])
    auto_email = StringField('Confirm Your Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number')
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name')
    user_type = SelectField('User Type', choices=[('Business', 'Business'), ('Individual', 'Individual')], validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    submit = SubmitField('Submit')

    def validate_auto_email(self, auto_email):
        if auto_email.data != self.email.data:
            raise ValidationError('Email addresses must match.')

# Serve favicon.ico from static directory
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

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
        range_to_update = f'Sheet1!A{row_count + 1}:N{row_count + 1}'
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
def fetch_data_from_sheet(email=None, max_retries=5, delay=2):
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
            
            # Filter by email if provided
            if email:
                df = df[df['Email'] == email]
            
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
        try:
            previous_debt_str = str(previous_submission['DebtLoan']).replace(',', '')
            previous_debt = float(previous_debt_str)
            if current_debt < previous_debt:
                badges.append("Debt Slayer!")
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting DebtLoan to float: {previous_submission['DebtLoan']}, error: {e}")

    logger.debug(f"Assigned badges for email {email}: {badges}")
    return badges

# Cache Plotly charts
@cache.memoize(timeout=3600)  # Cache for 1 hour
def generate_plots(email, health_score, cash_flow_score, debt_to_income_score, debt_interest_score, rank, all_users_df):
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
    breakdown_plot = fig_breakdown.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})

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
    comparison_plot = fig_comparison.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})

    return breakdown_plot, comparison_plot

# Send Email with course suggestion
def send_email(recipient_email, user_name, health_score, score_description, course_title, course_url, rank, total_users, language):
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    if not sender_email or not sender_password:
        logger.error("SENDER_EMAIL or SENDER_PASSWORD not set.")
        return False

    top_10_percent = (rank / total_users) <= 0.1
    subject = translations[language]['Top 10% Subject'] if top_10_percent else translations[language]['Score Report Subject'].format(user_name=user_name)
    html
