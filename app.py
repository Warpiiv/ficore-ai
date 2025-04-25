from flask import Flask, render_template, request, redirect, url_for
import subprocess
import time
import os

app = Flask(__name__)

# Ensure the Streamlit app is running
streamlit_process = None

def start_streamlit():
    global streamlit_process
    if streamlit_process is None:
        # Start Streamlit in a subprocess
        streamlit_process = subprocess.Popen(
            ["streamlit", "run", "dashboard.py", "--server.port", "8501"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Wait for Streamlit to start
        time.sleep(3)

# Start Streamlit when the Flask app starts
start_streamlit()

# Basic route for the homepage (assuming you have a form)
@app.route('/')
def home():
    return render_template('index.html')

# Example form submission route (simplified)
@app.route('/submit', methods=['POST'])
def submit():
    # Extract form data
    email = request.form.get('email')
    # Process form data, save to Google Sheets, calculate score, send email, etc.
    # (Reuse logic from Ficore AI Dev.ipynb)
    # For now, redirect to the dashboard with the user's email
    return redirect(url_for('dashboard', email=email))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    # Get the user's email from query parameters
    email = request.args.get('email', 'test@example.com')
    # Pass the email to the Streamlit app via query parameters
    streamlit_url = f"http://localhost:8501/?email={email}"
    return render_template('dashboard.html', streamlit_url=streamlit_url)

if __name__ == "__main__":
    try:
        app.run(debug=True, port=5000)
    finally:
        # Clean up Streamlit process on shutdown
        if streamlit_process:
            streamlit_process.terminate()
