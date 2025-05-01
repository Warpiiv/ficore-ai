# Ficore Africa Financial Health Score Application
# File: app.py
# Purpose: Flask app to calculate financial health scores, store data in Google Sheets, and render user dashboards
# Version: Updated May 1st, 2025, supports the "Click to Email" button in index.html with proper translations for both languages
# Repository: https://github.com/Warpiiv/ficore-ai

# Import required libraries
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
import re

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app with custom template and static folders
app = Flask(__name__, template_folder='ficore_templates', static_folder='static')

# Load environment variables from .env file
load_dotenv()

# Set Flask secret key for sessions and CSRF protection
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    logger.error("FLASK_SECRET_KEY environment variable not set. CSRF protection and sessions will fail.")
    raise Exception("FLASK_SECRET_KEY environment variable not set.")

# Set CSRF token expiration to 24 hours (86400 seconds)
app.config['WTF_CSRF_TIME_LIMIT'] = 86400

# Configure Flask-Caching for memoizing Google Sheets data
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Define translations for English and Hausa
translations = {
    'English': {
        'Welcome': 'Welcome',
        'Email': 'Email',
        'Your Financial Health Summary': 'Your Financial Health Summary:',
        'Your Financial Health Score': 'Your Financial Health Score',
        'Ranked': 'Ranked',
        'out of': 'out of',
        'users': 'users',
        'Strong Financial Health': 'Your score indicates strong financial health. Focus on investing the surplus funds to grow your wealth.',
        'Stable Finances': 'Your finances are stable but could improve. Consider saving more or reducing your expenses.',
        'Financial Strain': 'Your score suggests financial strain. Prioritize paying off debt and managing your expenses.',
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
        'Invest Wisely': 'Allocate surplus cash to low-risk investments like treasury bills or treasury bonds to grow your wealth.',
        'Scale': 'Scale',
        'Scale Smart': 'Reinvest profits into your business to expand operations sustainably.',
        'Build': 'Build',
        'Build Savings': 'Save 10% of your income monthly to create an emergency fund.',
        'Cut': 'Cut',
        'Cut Costs': 'Review needs and wants - check expenses and reduce non-essential spending to boost cash flow.',
        'Reduce': 'Reduce',
        'Reduce Debt': 'Prioritize paying off high-interest loans to ease financial strain.',
        'Boost': 'Boost',
        'Boost Income': 'Explore side hustles or new income streams to improve cash flow.',
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
        'Contact Us': 'Contact us at:',
        'for support': 'for support',
        'Click to Email': 'Click to Email',  # Added for the new email button
        'Ficore Africa Financial Health Score': 'Ficore Africa Financial Health Score',
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
        'User Information': 'User Information',
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
        'Error saving data. Please try again.': 'Error saving data. Please try again.',
        'Error retrieving data. Please try again.': 'Error retrieving data. Please try again.',
        'Error retrieving user data. Please try again.': 'Error retrieving user data. Please try again.',
        'An unexpected error occurred. Please try again.': 'An unexpected error occurred. Please try again.',
        'Session Expired': 'Your session has expired. Please refresh the page and try again.',
        'Top 10% Subject': '🔥 You\'re Top 10%! Your Ficore Score Report Awaits!',
        'Score Report Subject': '📊 Your Ficore Score Report is Ready, {user_name}!',
        'Email Body': '''
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #FFFFFF; margin: 0;">Ficore Africa Financial Health Score</h2>
                    <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Financial growth passport for Africa
                    </p>
                </div>
                <p>Dear {user_name},</p>
                <p>We have calculated your Ficore Africa Financial Health Score based on your recent submission.</p>
                <ul>
                    <li><strong>Score</strong>: {health_score}/100</li>
                    <li><strong>Advice</strong>: {score_description}</li>
                    <li><strong>Rank</strong>: #{rank} out of {total_users} users</li>
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
                    Have a Nice Day!.
                </p>
                <p>Best regards,<br>The Ficore Africa Team</p>
            </body>
            </html>
        ''',
        'First Health Score Completed!': 'First Health Score Completed!',
        'Financial Stability Achieved!': 'Financial Stability Achieved!',
        'Debt Slayer!': 'Debt Slayer!',
        'Submission Success': 'Your information is submitted successfully! Check your dashboard below 👇',
        'Check Inbox': 'Please check your inbox or junk folders if email doesn’t arrive in a few minutes.',
        'Your Financial Health Dashboard': 'Your Financial Health Dashboard'
    },
    'Hausa': {
        'Welcome': 'Barka da zuwa',
        'Email': 'Email',
        'Your Financial Health Summary': 'Takaitaccen Bayanai Akan Lafiyar Kuɗin Ku!',
        'Your Financial Health Score': 'Maki Da Lafiyar Kuɗin Ku Ta Samu:',
        'Ranked': 'Darajar Lafiyar Kuɗin Ku',
        'out of': 'Daga Cikin',
        'users': 'Dukkan Masu Amfani Da Ficore Zuwa Yanzu.',
        'Strong Financial Health': 'Makin ku yana nuna ƙarfin lafiyar kuɗinku. Ku Mai da hankali kan zuba hannun jari daga cikin kuɗin da ya rage muku don haɓaka dukiyarku.',
        'Stable Finances': 'Makin Kuɗin ku suna Nuni da kwanciyar hankali, amma zaku iya ingantashi duk da haka. Yi la’akari da adanawa ko rage wani bangare na kuɗin ta hanyar ajiya don gaba.',
        'Financial Strain': 'Makin ku yana nuna Akwai damuwar kuɗi. Ku Fifita biyan bashi sannan ku sarrafa kashe kuɗinku dakyau.',
        'Urgent Attention Needed': 'Makin Kuɗin ku suna Nuna buƙatar kulawa cikin gaggawa. Ku Nemi shawarar ƙwararru kuma Ku bincika dabarun farfadowa daga wannan yanayi.',
        'Score Breakdown': 'Rarraban Makin ku',
        'Chart Unavailable': 'Zanen Lissafi ba ya samuwa a wannan lokacin saboda Netowrk.',
        'Score Composition': 'Makin ku ya ƙunshi abubuwa uku',
        'Cash Flow': 'Kuɗin da Kuke Samu',
        'Cash Flow Description': 'Yana nuna adadin kuɗin da ya rage muku a hannu bayan Kun kashe kuɗi wajen biyan Bukatu. Maki mai ƙima yana nuna mafi kyawun alamar rike kuɗi.',
        'Debt-to-Income Ratio': 'Rabiyar Bashi zuwa Kuɗin shiga',
        'Debt-to-Income Description': 'Yana auna bashi dangane da kuɗin shiga. Ƙananan Makin rabiya yana nuna matakan bashi mai sauƙi.',
        'Debt Interest Burden': 'Nauyin Interest akan Bashi',
        'Debt Interest Description': 'Yana nuna tasirin ƙimar Interest a kan kuɗin ku. Ƙananan nauyi yana nufin ƙarancin damuwa daga Interest akan bashi.',
        'Balanced Components': 'Abubuwan da ke ciki suna nuna daidaitaccen lafiyar kuɗi. Ci gaba da kiyaye kuɗi ta hanya mai kyau kuma da ƙarancin bashi.',
        'Components Need Attention': 'Ɗaya ko fiye da abubuwan da ke ciki na iya buƙatar kulawa. Mai da hankali kan inganta samun kuɗi ko rage bashi.',
        'Components Indicate Challenges': 'Abubuwan da ke ciki suna nuna ƙalubale. Yi aiki kan ƙara kuɗin shiga, rage kashe kuɗin, ko rage Interest da kake biya akan bashi.',
        'Your Badges': 'Lambar Yabo',
        'No Badges Yet': 'Ba a sami Lambar Yabo ba tukuna. Ci gaba da Aiki da Ficore don samun Sabbin Lambobin Yabo!',
        'Recommended Learning': 'Shawari aka Koyon Inganta Neman Kudi da Ajiya.',
        'Recommended Course': 'Darasi da Aka Shawarta Maka',
        'Enroll in': 'Shiga ciki',
        'Enroll Now': 'Shiga Yanzu',
        'Quick Financial Tips': 'Shawarwari',
        'Invest': 'Saka hannun jari',
        'Invest Wisely': 'Sanya kuɗin da ya rage maka a cikin hannayen jari masu ƙarancin haɗari kamar takardun shaida daga Gwamnati ko Manyan Kamfanuwa don haɓaka dukiyarku.',
        'Scale': 'Faɗaɗa',
        'Scale Smart': 'Sake saka ribar kasuwancinku a cikin kasuwancin naku don faɗaɗa shi domin dorewa.',
        'Build': 'Gina',
        'Build Savings': 'Ajiye 10% na kuɗin shigarka a kowane wata don Samar da Asusun gaggawa domin rashin Lafiya ko jarabawa.',
        'Cut': 'Yanke',
        'Cut Costs': 'Kula da kashe kuɗinku kuma ku rage kashe kuɗin da ba dole ba don haɓaka arzikinku.',
        'Reduce': 'Rage',
        'Reduce Debt': 'Fifita biyan Bashi masu Interest don sauƙaƙe damuwar kuɗi.',
        'Boost': 'Ƙarfafa',
        'Boost Income': 'Bincika ayyukan a gefe ko ka nemi sabbin hanyoyin samun kuɗi don inganta Arzikinka.',
        'How You Compare': 'Kwatanta ku da Sauran Masu Amfani da Ficore',
        'Your Rank': 'Matsayin ku',
        'places you': 'ya sanya ku',
        'Top 10%': 'a cikin sama da kaso goma 10% na masu amfani da Ficore, yana nuna akwai kyawun lafiyar kuɗi idan aka kwatanta da Sauran Mutane.',
        'Top 30%': 'a cikin sama da kaso talatin 30%, yana nuna akwai kwanciyar hankali na kuɗi sama da yawancin Mutane.',
        'Middle Range': 'a cikin tsaka-tsaki, yana nuna akwai sarari don inganta samu domin hawa matsayi na gaba.',
        'Lower Range': 'a cikin mataki na ƙasa, yana nuna akwai buƙatar ku tsara kuɗinku dakyau cikin dabara daga yanzu.',
        'Regular Submissions': 'Amfani da Ficore akai-akai zai taimaka muku wajen bin diddigin ci gaban ku da kanku, don inganta matsayin Arzikinku.',
        'Whats Next': 'Me ke Gaba? Ku Duba Wadannan:',
        'Back to Home': 'Koma Sahfin Farko',
        'Provide Feedback': 'Danna Idan Kana da Shawara',
        'Join Waitlist': 'Masu Jiran Ficore Premium',
        'Book Consultancy': 'Jerin Masu Neman Shawara',
        'Contact Us': 'Tuntube Mu a',
        'for support': 'Don Tura Sako',
        'Click to Email': 'Danna Don Tura Sako',  # Added for the new email button
        'Ficore Africa Financial Health Score': 'Makin Lafiyar KuɗinKu Daga Ficore Africa',
        'Get Your Score': 'Sami makin lafiyar kuɗin ku don fahimtar keɓaɓɓun hanyoyin Ingantawa nan take!',
        'Personal Information': 'Bayanan Kai',
        'Enter your first name': 'Shigar da sunanka na farko',
        'First Name Required': 'Ana buƙatar sunan farko.',
        'Enter your last name (optional)': 'Shigar da sunanka na ƙarshe (na zaɓi)',
        'Enter your email': 'Shigar da email ɗinka',
        'Invalid Email': 'Da fatan za a shigar da adireshin email mai inganci.',
        'Confirm your email': 'Sake Tabbatar da email ɗinka',
        'Enter phone number (optional)': 'Shigar da lambar waya (na zaɓi)',
        'Language': 'Zabi Yare',
        'User Information': 'Bayanan Ka',
        'Enter your business name': 'Shigar da sunan kasuwancinka',
        'Business Name Required': 'Ana buƙatar sunan kasuwanci.',
        'User Type': 'Nau’in Mai Amfani da Ficore',
        'Financial Information': 'Bayanan Kuɗi',
        'Enter monthly income/revenue': 'Shigar da jimillar kuɗin shiga/kudin shigarku na wata-wata',
        'Enter monthly expenses/costs': 'Shigar da jimillar kashe kuɗinku/kudin wata-wata',
        'Enter total debt/loan amount': 'Shigar da jimillar bashi/lamuni',
        'Enter debt interest rate (%)': 'Shigar da Interest na bashin (%)',
        'Invalid Number': 'A shigar da lamba mai daidai.',
        'Submit': 'Mika Sako',
        'Error saving data. Please try again.': 'Anyi Kuskure wajen adana bayanai. Da fatan za a sake gwadawa.',
        'Error retrieving data. Please try again.': 'Anyi Kuskure wajen dawo da bayanai. Da fatan za a sake gwadawa.',
        'Error retrieving user data. Please try again.': 'Anyi Kuskure wajen dawo da bayanai masu amfani. Da fatan za a sake gwadawa.',
        'An unexpected error occurred. Please try again.': 'Wani kuskure wanda ba a zata ba ya faru. Da fatan za a sake gwadawa.',
        'Session Expired': 'Lokacin aikin ku ya ƙare. Da fatan za a sake shigar da shafin kuma a gwada sake.',
        'Top 10% Subject': '🔥 Kuna cikin Sama da kaso goma 10%! Rahoton Makin ku na Ficore Yana Jiran Ku!',
        'Score Report Subject': '📊 Rahoton Makin ku na Ficore Yana Shirye, {user_name}!',
        'Email Body': '''
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1E7F71; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #FFFFFF; margin: 0;">Makin Lafiyar Kuɗinku na Ficore Africa</h2>
                    <p style="font-style: italic; color: #E0F7FA; font-size: 0.9rem; margin: 5px 0 0 0;">
                        Tikitin ci gaban arciki na yan Afirka
                    </p>
                </div>
                <p>Barka Da Warhaka {user_name},</p>
                <p>Mun ƙididdige Makin Lafiyar Kuɗinku ta hanyar amfani da Ficore Africa bisa bayanan da kuka bayar.</p>
                <ul>
                    <li><strong>Maki</strong>: {health_score}/100</li>
                    <li><strong>Shawara</strong>: {score_description}</li>
                    <li><strong>Matsayi</strong>: #{rank} daga cikin {total_users} masu amfani</li>
                </ul>
                <p>Bi shawarar da ke sama don inganta arzikin ku. Muna nan don tallafa muku a kowane mataki— a fara aiki a yau don ƙarfafa arzikin ku domin kasuwancinku, burikanku, dakuma iyalanku!</p>
                <p style="margin-bottom: 10px;">
                    Kuna son ƙarin ilimi akan wannan? Duba wannan Darasi: 
                    <a href="{course_url}" style="display: inline-block; padding: 10px 20px; background-color: #FBC02D; color: #333; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">{course_title}</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Da fatan za a ba da shawara ko ra,ayi akan Ficore: 
                    <a href="{FEEDBACK_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #2E7D32; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Fom ɗin Shawara</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kuna son Shawarar daga Kwararru? Shiga jerin jiran Ficore Premium: 
                    <a href="{WAITLIST_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #1976D2; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Shiga Jerin Jira</a>
                </p>
                <p style="margin-bottom: 10px;">
                    Kuna buƙatar shawarwari keɓaɓɓu? 
                    <a href="{CONSULTANCY_FORM_URL}" style="display: inline-block; padding: 10px 20px; background-color: #388E3C; color: white; text-decoration: none; border-radius: 5px; font-size: 0.9rem;">Shiga Jerin Masu So</a>
                </p>
                <p style="margin-bottom: 10px;">
                    A huta Lafiya!
                </p>
                <p>Gaisuwa,<br>Daga Ƙungiyar Ficore Africa</p>
            </body>
            </html>
        ''',
        'First Health Score Completed!': 'Makin Lafiyar Arziki na Farko ya Kammala!',
        'Financial Stability Achieved!': 'Akwai Wadata!',
        'Debt Slayer!': 'Mai Ragargaza Bashi!',
        'Submission Success': 'An shigar da bayananka cikin nasara! Duba allon bayananka a ƙasa 👇',
        'Check Inbox': 'Da fatan za a duba akwatin saƙonku Inbox ko foldar na Spam ko Junk idan email ɗin bai zo ba cikin ƴan mintuna.',
        'Your Financial Health Dashboard': 'Allon Lafiyar Kuɗin Ku'
    }
}

# Define constants for Google Sheets and external URLs
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '13hbiMTMRBHo9MHjWwcugngY_aSiuxII67HCf03MiZ8I'
DATA_RANGE_NAME = 'Sheet1!A1:N'
RESULTS_SHEET_NAME = 'FicoreAfricaResults'
RESULTS_HEADER = ['Email', 'FicoreAfricaScore', 'FicoreAfricaRank']
FEEDBACK_FORM_URL = 'https://forms.gle/NkiLicSykLyMnhJk7'
WAITLIST_FORM_URL = 'https://forms.gle/3kXnJuDatTm8bT3x7'
CONSULTANCY_FORM_URL = 'https://forms.gle/rfHhpD71MjLpET2K9'
INVESTING_COURSE_URL = 'https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI'
SAVINGS_COURSE_URL = 'https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI'
DEBT_COURSE_URL = 'https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI'
RECOVERY_COURSE_URL = 'https://youtube.com/@ficore.africa?si=myoEpotNALfGK4eI'
PREDETERMINED_HEADERS = [
    'Timestamp', 'BusinessName', 'IncomeRevenue', 'ExpensesCosts', 'DebtLoan',
    'DebtInterestRate', 'AutoEmail', 'PhoneNumber', 'FirstName', 'LastName',
    'UserType', 'Email', 'Badges', 'Language'
]

# Define Flask-WTF form for user submissions
class SubmissionForm(FlaskForm):
    business_name = StringField('Business Name', validators=[DataRequired()])
    income_revenue = StringField('Income Revenue', validators=[DataRequired()])
    expenses_costs = StringField('Expenses Costs', validators=[DataRequired()])
    debt_loan = StringField('Debt Loan', validators=[DataRequired()])
    debt_interest_rate = StringField('Debt Interest Rate', validators=[DataRequired()])
    auto_email = StringField('Confirm Your Email', validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number')
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name')
    user_type = SelectField('User Type', choices=[('Business', 'Business'), ('Individual', 'Individual')], validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    language = SelectField('Language', choices=[('English', 'English'), ('Hausa', 'Hausa')], validators=[DataRequired()])
    submit = SubmitField('Submit')

    # Validate email confirmation
    def validate_auto_email(self, auto_email):
        if auto_email.data != self.email.data:
            raise ValidationError('Email addresses must match.')

    # Validate numeric fields
    def validate_income_revenue(self, income_revenue):
        try:
            value = float(re.sub(r'[,]', '', income_revenue.data))
            if value < 0:
                raise ValidationError('Income/Revenue must be a non-negative number.')
        except ValueError:
            raise ValidationError('Income/Revenue must be a valid number.')

    def validate_expenses_costs(self, expenses_costs):
        try:
            value = float(re.sub(r'[,]', '', expenses_costs.data))
            if value < 0:
                raise ValidationError('Expenses/Costs must be a non-negative number.')
        except ValueError:
            raise ValidationError('Expenses/Costs must be a valid number.')

    def validate_debt_loan(self, debt_loan):
        try:
            value = float(re.sub(r'[,]', '', debt_loan.data))
            if value < 0:
                raise ValidationError('Debt/Loan must be a non-negative number.')
        except ValueError:
            raise ValidationError('Debt/Loan must be a valid number.')

    def validate_debt_interest_rate(self, debt_interest_rate):
        try:
            value = float(re.sub(r'[,]', '', debt_interest_rate.data))
            if value < 0:
                raise ValidationError('Debt Interest Rate must be a non-negative number.')
        except ValueError:
            raise ValidationError('Debt Interest Rate must be a valid number.')

# Route to serve favicon
@app.route('/favicon.ico')
def favicon():
    logger.info("Serving favicon.ico")
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Root route to render submission form
@app.route('/')
def home():
    logger.info("Accessing root route")
    form = SubmissionForm()
    language = request.args.get('language', 'English')
    if language not in translations:
        language = 'English'
    return render_template('index.html', form=form, translations=translations, language=language)

# Authenticate with Google Sheets using service account
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

# Fetch current headers from Google Sheet
def get_sheet_headers():
    try:
        service = authenticate_google_sheets()
        if not service:
            logger.error("Failed to authenticate with Google Sheets.")
            return None
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A1:N1').execute()
        headers = result.get('values', [[]])[0]
        return headers
    except Exception as e:
        logger.error(f"Error fetching sheet headers: {e}")
        return None

# Set or update predefined headers in Google Sheet
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
            range='Sheet1!A1:N1',
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info("Sheet1 headers updated to predetermined values.")
        return True
    except Exception as e:
        logger.error(f"Error setting headers: {e}")
        return False

# Get current row count in Google Sheet
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

# Append form data to Google Sheet
def append_to_sheet(data):
    try:
        service = authenticate_google_sheets()
        if not service:
            logger.error("Failed to authenticate with Google Sheets.")
            return False
        sheet = service.spreadsheets()

        # Check and update headers if necessary
        current_headers = get_sheet_headers()
        if not current_headers or current_headers != PREDETERMINED_HEADERS:
            if not set_sheet_headers():
                logger.error("Failed to set sheet headers.")
                return False

        row_count = get_row_count()
        if row_count == 0:
            if not set_sheet_headers():
                logger.error("Failed to set sheet headers.")
                return False
            row_count = 1

        if len(data) != len(PREDETERMINED_HEADERS):
            logger.error(f"Data length ({len(data)}) does not match headers ({len(PREDETERMINED_HEADERS)}): {data}")
            return False

        range_to_update = f'Sheet1!A{row_count + 1}:N{row_count + 1}'
        body = {'values': [data]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption='RAW',
            body=body
        ).execute()
        logger.info(f"Appended data to sheet at row {row_count + 1}: {data}")
        time.sleep(1)
        return True
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")
        return False

# Fetch data from Google Sheet with caching and retry logic
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
            
            logger.debug(f"Attempt {attempt + 1}: Fetched {len(rows)} rows with headers: {headers}")
            
            # Adjust rows to match expected columns
            adjusted_rows = []
            for row in rows:
                if len(row) < len(expected_columns):
                    row.extend([''] * (len(expected_columns) - len(row)))
                elif len(row) > len(expected_columns):
                    row = row[:len(expected_columns)]
                adjusted_rows.append(row)
            
            df = pd.DataFrame(adjusted_rows, columns=expected_columns)
            
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Set default language to 'English' if Language is empty
            df['Language'] = df['Language'].replace('', 'English')
            # Ensure Language is a valid key in translations
            valid_languages = list(translations.keys())
            df['Language'] = df['Language'].apply(lambda x: x if x in valid_languages else 'English')
            
            if email:
                df = df[df['Email'] == email]
            
            logger.info(f"Successfully fetched data: {len(df)} rows for email {email if email else 'all'}")
            return df
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
                continue
            logger.error("Max retries reached while fetching data.")
            return None

# Calculate financial health score based on user inputs
def calculate_health_score(df):
    try:
        if df.empty:
            logger.warning("Empty DataFrame passed to calculate_health_score.")
            return df
        
        # Convert string inputs to floats, handling commas
        for col in ['IncomeRevenue', 'ExpensesCosts', 'DebtLoan', 'DebtInterestRate']:
            df[col] = df[col].apply(lambda x: float(re.sub(r'[,]', '', str(x))) if isinstance(x, str) and x else 0.0)

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

        # Assign score descriptions and recommended courses
        def score_description_and_course(row):
            score = row['HealthScore']
            cash_flow = row['CashFlowRatio']
            debt_to_income = row['DebtToIncomeRatio']
            debt_interest = row['DebtInterestBurden']
            
            if score >= 75:
                return ('Stable Income; invest excess now',
                        'Ficore Simplified Investing Course: How to Invest in 2025 for Better Gains',
                        INVESTING_COURSE_URL)
            elif score >= 50:
                if cash_flow < 0.3 or debt_interest > 0.5:
                    return ('At Risk; manage your expense!',
                            'Ficore Debt and Expense Management: Regain Control in 2025',
                            DEBT_COURSE_URL)
                return ('Moderate; save something monthly!',
                        'Ficore Savings Mastery: Building a Financial Safety Net in 2025',
                        SAVINGS_COURSE_URL)
            elif score >= 25:
                if debt_to_income > 0.5 or debt_interest > 0.5:
                    return ('At Risk; pay off debt, manage your expense!',
                            'Ficore Debt and Expense Management: Regain Control in 2025',
                            DEBT_COURSE_URL)
                return ('At Risk; manage your expense!',
                        'Ficore Debt and Expense Management: Regain Control in 2025',
                        DEBT_COURSE_URL)
            else:
                if debt_to_income > 0.5 or cash_flow < 0.3:
                    return ('Critical; add source of income! pay off debt! manage your expense!',
                            'Ficore Financial Recovery: First Steps to Stability in 2025',
                            RECOVERY_COURSE_URL)
                return ('Critical; seek financial help and advice!',
                        'Ficore Financial Recovery: First Steps to Stability in 2025',
                        RECOVERY_COURSE_URL)

        df[['ScoreDescription', 'CourseTitle', 'CourseURL']] = df.apply(
            score_description_and_course, axis=1, result_type='expand')
        return df
    except Exception as e:
        logger.error(f"Error calculating health score: {e}")
        raise

# Assign badges based on user achievements
def assign_badges(user_df, all_users_df):
    badges = []
    if user_df.empty:
        logger.warning("Empty user_df in assign_badges.")
        return badges
    
    # Sort by Timestamp to get the most recent submission
    try:
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', dayfirst=True, errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
    except Exception as e:
        logger.error(f"Error parsing timestamps in assign_badges: {e}")
        raise
    
    user_row = user_df.iloc[0]
    
    email = user_row['Email']
    health_score = user_row['HealthScore']
    language = user_row['Language']
    
    # Validate language
    if language not in translations:
        logger.warning(f"Invalid language '{language}' for user {email}. Defaulting to English.")
        language = 'English'
    
    # Badge for first submission
    if len(user_df) == 1:
        badges.append(translations[language]['First Health Score Completed!'])
    
    # Badge for stable finances
    if health_score >= 50:
        badges.append(translations[language]['Financial Stability Achieved!'])
    
    # Badge for low debt
    debt_to_income = user_row['DebtToIncomeRatio']
    if debt_to_income < 0.3:
        badges.append(translations[language]['Debt Slayer!'])
    
    return badges

# Send email with score report to user
def send_email(to_email, user_name, health_score, score_description, rank, total_users, course_title, course_url, language):
    try:
        # Ensure rank is an integer
        rank = int(rank)
        smtp_server = os.environ.get('SMTP_SERVER')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        
        if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
            logger.error("SMTP configuration environment variables not set.")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        subject = translations[language]['Top 10% Subject'] if rank <= total_users * 0.1 else translations[language]['Score Report Subject'].format(user_name=user_name)
        msg['Subject'] = subject
        
        body = translations[language]['Email Body'].format(
            user_name=user_name,
            health_score=health_score,
            score_description=score_description,
            rank=rank,
            total_users=total_users,
            course_url=course_url,
            course_title=course_title,
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
        )
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email sent to {to_email}")
        return True
    except ValueError as e:
        logger.error(f"Error converting rank to integer: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return False

# Generate pie chart for score breakdown
def generate_breakdown_plot(user_df):
    try:
        if user_df.empty:
            return None
        
        # Sort by Timestamp to get the most recent submission
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', dayfirst=True, errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        user_row = user_df.iloc[0]
        
        labels = ['Cash Flow', 'Debt-to-Income', 'Debt Interest']
        values = [
            user_row['NormCashFlow'] * 100 / 3,
            user_row['NormDebtToIncome'] * 100 / 3,
            user_row['NormDebtInterest'] * 100 / 3
        ]
        fig = px.pie(names=labels, values=values, title='Score Breakdown')
        fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.error(f"Error generating breakdown plot: {e}")
        return None

# Generate histogram for score comparison
def generate_comparison_plot(user_df, all_users_df):
    try:
        if user_df.empty or all_users_df.empty:
            return None
        
        # Sort by Timestamp to get the most recent submission
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', dayfirst=True, errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        user_score = user_df.iloc[0]['HealthScore']
        
        scores = all_users_df['HealthScore'].astype(float)
        fig = px.histogram(
            x=scores,
            nbins=20,
            title='How Your Score Compares',
            labels={'x': 'Financial Health Score', 'y': 'Number of Users'}
        )
        fig.add_vline(x=user_score, line_dash="dash", line_color="red")
        fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception as e:
        logger.error(f"Error generating comparison plot: {e}")
        return None

# Handle form submission and render dashboard
@app.route('/submit', methods=['POST'])
def submit():
    logger.info("Received /submit request")
    form = SubmissionForm()
    language = form.language.data if form.language.data in translations else 'English'
    
    try:
        # Validate form inputs
        logger.info("Validating form submission")
        if not form.validate_on_submit():
            logger.warning(f"Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    # Check if the error is related to CSRF token expiration
                    if 'csrf_token' in field and 'expired' in error.lower():
                        flash(translations[language]['Session Expired'], 'error')
                    else:
                        flash(error, 'error')
            return redirect(url_for('home', language=language))
        
        logger.info("Form validated successfully")
        
        # Prepare submission data
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = [
            timestamp,
            form.business_name.data,
            form.income_revenue.data,
            form.expenses_costs.data,
            form.debt_loan.data,
            form.debt_interest_rate.data,
            form.auto_email.data,
            form.phone_number.data,
            form.first_name.data,
            form.last_name.data,
            form.user_type.data,
            form.email.data,
            '',  # Badges (updated later)
            form.language.data
        ]
        
        # Append data to Google Sheet
        logger.info("Appending data to Google Sheet")
        if not append_to_sheet(data):
            flash(translations[language]['Error saving data. Please try again.'], 'error')
            return redirect(url_for('home', language=language))
        
        # Fetch all user data
        logger.info("Fetching all user data from Google Sheet")
        all_users_df = fetch_data_from_sheet()
        if all_users_df is None:
            flash(translations[language]['Error retrieving data. Please try again.'], 'error')
            return redirect(url_for('home', language=language))
        
        # Fetch user-specific data
        logger.info(f"Fetching user data for email: {form.email.data}")
        user_df = fetch_data_from_sheet(email=form.email.data)
        if user_df is None or user_df.empty:
            flash(translations[language]['Error retrieving user data. Please try again.'], 'error')
            return redirect(url_for('home', language=language))
        
        # Calculate scores
        logger.info("Calculating health scores")
        all_users_df = calculate_health_score(all_users_df)
        user_df = calculate_health_score(user_df)
        
        # Assign badges
        logger.info("Assigning badges")
        badges = assign_badges(user_df, all_users_df)
        user_df['Badges'] = ','.join(badges)
        
        # Update badges in Google Sheet for the most recent submission
        logger.info("Updating badges in Google Sheet")
        user_df['Timestamp'] = pd.to_datetime(user_df['Timestamp'], format='mixed', dayfirst=True, errors='coerce')
        user_df = user_df.sort_values('Timestamp', ascending=False)
        most_recent_row = user_df.iloc[0]
        user_row_index = all_users_df[all_users_df['Email'] == form.email.data].index
        if not user_row_index.empty:
            # Find the index of the most recent submission
            all_users_df['Timestamp'] = pd.to_datetime(all_users_df['Timestamp'], format='mixed', dayfirst=True, errors='coerce')
            user_rows = all_users_df[all_users_df['Email'] == form.email.data]
            most_recent_idx = user_rows['Timestamp'].idxmax()
            row_index = most_recent_idx + 2  # +2 for header and 1-based indexing
            service = authenticate_google_sheets()
            if service:
                sheet = service.spreadsheets()
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f'Sheet1!M{row_index}',
                    valueInputOption='RAW',
                    body={'values': [[','.join(badges)]]}
                ).execute()
        
        # Calculate user rank
        logger.info("Calculating user rank")
        all_users_df = all_users_df.sort_values('HealthScore', ascending=False).reset_index(drop=True)
        user_rows = all_users_df[all_users_df['Email'] == form.email.data]
        if user_rows.empty:
            logger.error(f"User {form.email.data} not found in all_users_df after submission.")
            flash(translations[language]['Error retrieving user data. Please try again.'], 'error')
            return redirect(url_for('home', language=language))
        # Use the most recent submission for ranking
        user_rows = user_rows.sort_values('Timestamp', ascending=False)
        user_index = all_users_df.index[all_users_df['Email'] == form.email.data].tolist()[0]
        rank = user_index + 1
        total_users = len(all_users_df.drop_duplicates(subset=['Email']))
        
        # Prepare user_data for the chart
        logger.info("Preparing user_data for dashboard")
        user_data = {
            'income': float(re.sub(r'[,]', '', form.income_revenue.data)) if form.income_revenue.data else 0.0,
            'expenses': float(re.sub(r'[,]', '', form.expenses_costs.data)) if form.expenses_costs.data else 0.0,
            'debt': float(re.sub(r'[,]', '', form.debt_loan.data)) if form.debt_loan.data else 0.0
        }
        
        # Use the health_score from the most recent submission
        health_score = most_recent_row['HealthScore']
        
        # Prepare peer_data (average health score of all users)
        logger.info("Preparing peer_data for dashboard")
        average_score = all_users_df['HealthScore'].mean() if not all_users_df.empty else 50.0
        peer_data = {
            'averageScore': round(average_score, 2)
        }
        
        # Generate dashboard plots (your existing Plotly plots)
        logger.info("Generating dashboard plots")
        breakdown_plot = generate_breakdown_plot(user_df)
        comparison_plot = generate_comparison_plot(user_df, all_users_df)
        
        # Send score report email
        logger.info("Sending score report email")
        email_sent = send_email(
            to_email=form.email.data,
            user_name=form.first_name.data,
            health_score=health_score,
            score_description=most_recent_row['ScoreDescription'],
            rank=rank,
            total_users=total_users,
            course_title=most_recent_row['CourseTitle'],
            course_url=most_recent_row['CourseURL'],
            language=form.language.data
        )
        if not email_sent:
            logger.warning(f"Failed to send email to {form.email.data}, but proceeding to render dashboard.")
        
        # Render dashboard with user data, including the new variables
        logger.info("Rendering dashboard")
        return render_template(
            'dashboard.html',
            translations=translations,
            language=form.language.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data or '',
            email=form.email.data,
            user_data=user_data,  # Added for chart
            health_score=health_score,  # Added for chart
            peer_data=peer_data,  # Added for chart
            rank=rank,
            total_users=total_users,
            badges=badges,
            course_title=most_recent_row['CourseTitle'],
            course_url=most_recent_row['CourseURL'],
            breakdown_plot=breakdown_plot,
            comparison_plot=comparison_plot,
            personalized_message=most_recent_row['ScoreDescription'],
            FEEDBACK_FORM_URL=FEEDBACK_FORM_URL,
            WAITLIST_FORM_URL=WAITLIST_FORM_URL,
            CONSULTANCY_FORM_URL=CONSULTANCY_FORM_URL
        )
    except Exception as e:
        logger.error(f"Error processing submission: {str(e)}\n{traceback.format_exc()}")
        flash(translations[language]['An unexpected error occurred. Please try again.'], 'error')
        return redirect(url_for('home', language=language))

# Run Flask app in debug mode for local development
if __name__ == '__main__':
    app.run(debug=True)
