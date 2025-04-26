from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import bcrypt
import logging
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='ficore_templates')
app.secret_key = os.urandom(24)

# Load environment variables
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Define models
class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    submissions = relationship('Submission', back_populates='user')

    def get_id(self):
        return str(self.id)

class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    business_name = Column(String(255))
    income_revenue = Column(Float, nullable=False)
    expenses_costs = Column(Float, nullable=False)
    debt_loan = Column(Float, nullable=False)
    debt_interest_rate = Column(Float, nullable=False)
    phone_number = Column(String(20))
    user_type = Column(String(50))
    health_score = Column(Float)
    score_description = Column(String)
    course_title = Column(String)
    course_url = Column(String)
    badges = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='submissions')

# Create tables
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    session = Session()
    user = session.query(User).get(int(user_id))
    session.close()
    return user

# Constants
FEEDBACK_FORM_URL = 'https://forms.gle/NkiLicSykLyMnhJk7'
WAITLIST_FORM_URL = 'https://forms.gle/3kXnJuDatTm8bT3x7'
CONSULTANCY_FORM_URL = 'https://forms.gle/rfHhpD71MjLpET2K9'
INVESTING_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
SAVINGS_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
DEBT_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
RECOVERY_COURSE_URL = 'https://youtube.com/@ficore.ai.africa?si=myoEpotNALfGK4eI'
PREDETERMINED_HEADERS = [
    'timestamp', 'business_name', 'income_revenue', 'expenses_costs', 'debt_loan',
    'debt_interest_rate', 'phone_number', 'user_type', 'health_score', 'score_description',
    'course_title', 'course_url', 'badges'
]

# Calculate Financial Health Score
def calculate_health_score(df):
    # Ensure numeric columns are float and handle missing/invalid values
    numeric_cols = ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['HealthScore'] = 0.0
    df['IncomeRevenueSafe'] = df['income_revenue'].replace(0, 1e-10)
    df['CashFlowRatio'] = (df['income_revenue'] - df['expenses_costs']) / df['IncomeRevenueSafe']
    df['DebtToIncomeRatio'] = df['debt_loan'] / df['IncomeRevenueSafe']
    df['DebtInterestBurden'] = df['debt_interest_rate'].clip(lower=0) / 20
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

# Assign badges
def assign_badges(user_df, all_user_submissions):
    badges = []
    user_row = user_df.iloc[0]
    email = user_row['email']
    health_score = user_row['HealthScore']
    current_debt = user_row['debt_loan']

    user_submissions = all_user_submissions[all_user_submissions['email'] == email]
    if len(user_submissions) == 1:
        badges.append("First Health Score Completed!")
    if health_score > 80:
        badges.append("Financial Stability Achieved!")
    if len(user_submissions) > 1:
        previous_submission = user_submissions.iloc[-2]
        previous_debt = float(previous_submission['debt_loan'])
        if current_debt < previous_debt:
            badges.append("Debt Slayer!")

    logger.debug(f"Assigned badges for email {email}: {badges}")
    return badges

# Send Email
def send_email(recipient_email, user_name, health_score, score_description, course_title, course_url, rank, total_users):
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
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
                logger.info(f"Email successfully sent to {recipient_email}")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
    logger.error(f"Failed to send email to {recipient_email} after 3 attempts")
    return False

# Routes
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('register.html')

        session = Session()
        existing_user = session.query(User).filter_by(email=email).first()
        if existing_user:
            session.close()
            flash('Email already registered. Please log in.', 'error')
            return render_template('register.html')

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = User(email=email, password_hash=password_hash, first_name=first_name, last_name=last_name)
        session.add(new_user)
        session.commit()
        session.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        session = Session()
        user = session.query(User).filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user)
            session.close()
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        session.close()
        flash('Invalid email or password.', 'error')
        return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Validate required fields
        required_fields = ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate']
        for field in required_fields:
            if field not in request.form or not request.form[field]:
                raise ValueError(f"Missing or empty required field: {field}")

        timestamp = datetime.utcnow()
        business_name = request.form.get('business_name', '')
        income_revenue = float(request.form['income_revenue'].replace(',', ''))
        expenses_costs = float(request.form['expenses_costs'].replace(',', ''))
        debt_loan = float(request.form['debt_loan'].replace(',', ''))
        debt_interest_rate = float(request.form['debt_interest_rate'].replace(',', ''))
        phone_number = request.form.get('phone_number', '')
        user_type = request.form.get('user_type', 'individual')
        email = request.form.get('email', 'anonymous@ficore.ai')

        if any(x < 0 for x in [income_revenue, expenses_costs, debt_loan, debt_interest_rate]):
            raise ValueError("Numeric fields must be non-negative.")

        data = {
            'timestamp': timestamp.isoformat(),
            'business_name': business_name,
            'income_revenue': income_revenue,
            'expenses_costs': expenses_costs,
            'debt_loan': debt_loan,
            'debt_interest_rate': debt_interest_rate,
            'phone_number': phone_number,
            'user_type': user_type,
            'email': email
        }

        if current_user.is_authenticated:
            data['user_id'] = current_user.id

        session = Session()
        all_submissions = pd.read_sql(session.query(Submission).statement, session.bind)
        session.close()

        if all_submissions.empty:
            all_submissions = pd.DataFrame(columns=PREDETERMINED_HEADERS + ['email'])

        # Clean all_submissions to ensure required columns exist and are numeric
        required_columns = ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate', 'email']
        for col in required_columns:
            if col not in all_submissions.columns:
                all_submissions[col] = 0 if col != 'email' else 'anonymous@ficore.ai'
        # Convert numeric columns to float, replacing invalid values with 0
        numeric_cols = ['income_revenue', 'expenses_costs', 'debt_loan', 'debt_interest_rate']
        for col in numeric_cols:
            all_submissions[col] = pd.to_numeric(all_submissions[col], errors='coerce').fillna(0)

        temp_df = pd.DataFrame([data])
        temp_df = calculate_health_score(temp_df)

        new_badges = []
        if current_user.is_authenticated:
            new_badges = assign_badges(temp_df, all_submissions)
            data['health_score'] = temp_df.iloc[0]['HealthScore']
            data['score_description'] = temp_df.iloc[0]['ScoreDescription']
            data['course_title'] = temp_df.iloc[0]['CourseTitle']
            data['course_url'] = temp_df.iloc[0]['CourseURL']
            data['badges'] = ",".join(new_badges)

            session = Session()
            new_submission = Submission(**data)
            session.add(new_submission)
            session.commit()
            session.close()

        # Recalculate scores for all submissions
        session = Session()
        all_submissions = pd.read_sql(session.query(Submission).statement, session.bind)
        session.close()

        # Clean again to ensure consistency
        for col in required_columns:
            if col not in all_submissions.columns:
                all_submissions[col] = 0 if col != 'email' else 'anonymous@ficore.ai'
        for col in numeric_cols:
            all_submissions[col] = pd.to_numeric(all_submissions[col], errors='coerce').fillna(0)

        if not all_submissions.empty:
            all_submissions = calculate_health_score(all_submissions)
            all_submissions = all_submissions.sort_values(by='HealthScore', ascending=False)
            all_submissions['Rank'] = range(1, len(all_submissions) + 1)
        else:
            all_submissions = pd.DataFrame(columns=list(temp_df.columns) + ['Rank'])

        user_df = all_submissions[all_submissions['email'] == email] if current_user.is_authenticated else temp_df
        user_row = user_df.iloc[-1]
        health_score = user_row['HealthScore']
        score_description = user_row['ScoreDescription']
        rank = user_row.get('Rank', len(all_submissions) + 1)
        total_users = len(all_submissions)

        user_name = f"{current_user.first_name} {current_user.last_name}" if current_user.is_authenticated else "User"
        email_sent = False
        if email != 'anonymous@ficore.ai':
            email_sent = send_email(email, user_name, health_score, user_row['score_description'],
                                   user_row['course_title'], user_row['course_url'], rank, total_users)

        personalized_message = "🎉 Congratulations, you earned your first badge: Financial Explorer!" if current_user.is_authenticated and "First Health Score Completed!" in new_badges else f"🎉 Great job! You earned a new badge: {new_badges[-1]}" if current_user.is_authenticated and new_badges else ""
        if not email_sent and email != 'anonymous@ficore.ai':
            personalized_message += " ⚠️ Unable to send email report. Please check your spam folder or contact support."

        first_name = current_user.first_name if current_user.is_authenticated else "User"
        return render_template(
            'success.html',
            first_name=first_name,
            health_score=health_score,
            score_description=score_description,
            rank=rank,
            total_users=total_users,
            email=email,
            personalized_message=personalized_message
        )
    except ValueError as ve:
        logger.error(f"Validation error in form submission: {ve}")
        return render_template('error.html', error_message=f"Invalid input: {str(ve)}. Please check your data and try again.")
    except Exception as e:
        logger.error(f"Error in form submission: {e}")
        return render_template('error.html', error_message=f"Error processing your submission: {str(e)}. Please try again later.")

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        session = Session()
        all_submissions = pd.read_sql(session.query(Submission).statement, session.bind)
        session.close()

        if all_submissions.empty:
            return render_template('error.html', error_message='No submissions found in the database. Please submit your financial data to view your dashboard.')

        all_submissions = calculate_health_score(all_submissions)
        all_submissions = all_submissions.sort_values(by='HealthScore', ascending=False)
        all_submissions['Rank'] = range(1, len(all_submissions) + 1)

        user_df = all_submissions[all_submissions['user_id'] == current_user.id]
        if user_df.empty:
            return render_template('error.html', error_message='You haven’t submitted any financial data yet. Please submit your data to view your dashboard.')

        user_row = user_df.iloc[-1]
        health_score = user_row['HealthScore']
        rank = user_row['Rank']
        total_users = len(all_submissions)
        score_description = user_row['score_description']
        course_title = user_row['course_title']
        course_url = user_row['course_url']
        badges = user_row['badges'].split(",") if user_row['badges'] else []
        cash_flow_score = round(user_row['NormCashFlow'] * 100, 2)
        debt_to_income_score = round(user_row['NormDebtToIncome'] * 100, 2)
        debt_interest_score = round(user_row['NormDebtInterest'] * 100, 2)

        personalized_message = request.args.get('personalized_message', '')

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
                x=list(range(1, len(all_submissions) + 1)),
                y=all_submissions['HealthScore'],
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
            comparison_plot=comparison_plot
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return render_template('error.html', error_message=f"Error rendering dashboard: {str(e)}. Please try again later.")

@app.route('/history')
@login_required
def history():
    try:
        session = Session()
        user_submissions = pd.read_sql(
            session.query(Submission).filter_by(user_id=current_user.id).statement,
            session.bind
        )
        session.close()

        if user_submissions.empty:
            return render_template('error.html', error_message='No submission history found.')

        user_submissions = calculate_health_score(user_submissions)
        submissions_list = user_submissions.to_dict('records')

        fig_trend = px.line(
            user_submissions,
            x='timestamp',
            y='HealthScore',
            title="Financial Health Score Trend Over Time",
            labels={"timestamp": "Date", "HealthScore": "Health Score"},
            markers=True
        )
        trend_plot = fig_trend.to_html(full_html=False, include_plotlyjs=False)

        return render_template(
            'history.html',
            submissions=submissions_list,
            trend_plot=trend_plot
        )
    except Exception as e:
        logger.error(f"Error rendering history: {e}")
        return render_template('error.html', error_message=f"Error rendering history: {str(e)}. Please try again later.")

@app.route('/download_report/<email>')
def download_report(email):
    try:
        session = Session()
        all_submissions = pd.read_sql(session.query(Submission).statement, session.bind)
        session.close()

        user_df = all_submissions[all_submissions['email'] == email]
        if user_df.empty:
            return render_template('error.html', error_message='No submissions found for this email. Please submit your financial data.')

        user_row = user_df.iloc[-1]
        health_score = user_row['HealthScore']
        score_description = user_row['score_description']
        all_submissions = calculate_health_score(all_submissions)
        all_submissions = all_submissions.sort_values(by='HealthScore', ascending=False)
        all_submissions['Rank'] = range(1, len(all_submissions) + 1)
        rank = all_submissions[all_submissions['email'] == email]['Rank'].iloc[-1]
        total_users = len(all_submissions)

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFillColor(colors.darkgreen)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width / 2, height - 50, "Ficore AI Financial Health Report")

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Oblique", 12)
        c.drawCentredString(width / 2, height - 70, "Financial Growth Passport for Africa")

        c.setFont("Helvetica", 12)
        first_name = current_user.first_name if current_user.is_authenticated else "User"
        last_name = current_user.last_name if current_user.is_authenticated else ""
        c.drawString(50, height - 120, f"Name: {first_name} {last_name}")
        c.drawString(50, height - 140, f"Email: {email}")
        c.drawString(50, height - 160, f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}")

        c.setFillColor(colors.darkgreen)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 200, f"Financial Health Score: {health_score}/100")

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 230, f"Advice: {score_description}")

        c.drawString(50, height - 260, f"Rank: #{int(rank)} out of {total_users} users")

        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(colors.grey)
        c.drawCentredString(width / 2, 30, "Powered by Ficore AI")

        c.showPage()
        c.save()

        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"ficore_financial_report_{email}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        return render_template('error.html', error_message=f"Error generating PDF report: {str(e)}. Please try again later.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
