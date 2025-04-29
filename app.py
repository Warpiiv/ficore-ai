<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Track your financial health with Ficore Africa. See your score, earn badges, and get smart insights.">
    <meta name="keywords" content="ficore africa, financial health, dashboard, Africa SME finance, smart insights">
    <meta name="author" content="Ficore Africa">
    <title>Ficore Africa - Your Financial Health Dashboard</title>
    <link href="{{ url_for('static', filename='css/bootstrap.min.css') }}" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Open+Sans:wght@300;400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <script defer src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        body {
            font-family: 'Open Sans', sans-serif;
            background: linear-gradient(135deg, #E3F2FD, #F5F7FA);
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }
        .container {
            max-width: 1000px;
            margin: auto;
        }
        .card-base {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), inset 0 1px 3px rgba(255, 255, 255, 0.3);
            margin-bottom: 1.5rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid #E0E0E0;
        }
        .card-base:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), inset 0 1px 3px rgba(255, 255, 255, 0.3);
        }
        .card-header-modern {
            background: linear-gradient(135deg, #2E7D32, #0288D1);
            color: white;
            padding: 1rem;
            border-radius: 12px 12px 0 0;
            text-align: center;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
            font-size: 1.75rem;
            white-space: nowrap;
            border-bottom: 3px solid #1B5E20;
            margin-bottom: 0.5rem;
        }
        .card-body {
            padding: 1.25rem;
        }
        .section-divider-modern {
            border: none;
            height: 2px;
            background: linear-gradient(to right, transparent, #4CAF50, transparent);
            margin: 1rem 0;
            padding-top: 1rem;
        }
        h2, h3 {
            color: #2E7D32;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        h3 {
            font-size: 1.35rem;
        }
        .subheading {
            color: #0288D1;
            font-style: italic;
            font-size: 1.1rem;
        }
        .badge-modern {
            display: inline-block;
            background: linear-gradient(135deg, #81C784, #4CAF50);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            margin: 5px;
            font-size: 0.9rem;
            font-family: 'Open Sans', sans-serif;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .badge-modern i {
            margin-right: 5px;
        }
        .badge-modern:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        .alert {
            border-radius: 8px;
            font-weight: 500;
            margin-bottom: 1.5rem;
        }
        .alert-success {
            background-color: #D4EDDA;
            color: #155724;
        }
        .alert-danger {
            background-color: #F8D7DA;
            color: #721C24;
        }
        .btn-primary-modern {
            background: linear-gradient(135deg, #2E7D32, #0288D1);
            border: none;
            padding: 10px 20px;
            font-family: 'Open Sans', sans-serif;
            font-weight: 600;
            border-radius: 8px;
            color: white;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .btn-primary-modern:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            background: linear-gradient(135deg, #1B5E20, #01579B);
            border: 1px solid #4CAF50;
        }
        .btn-secondary-modern {
            background: linear-gradient(135deg, #F57C00, #FF9800);
            border: none;
            padding: 10px 20px;
            font-family: 'Open Sans', sans-serif;
            font-weight: 600;
            border-radius: 8px;
            color: white;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .btn-secondary-modern:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            background: linear-gradient(135deg, #E65100, #F57C00);
            border: 1px solid #FF9800;
        }
        .course-link-modern {
            display: inline-block;
            background: linear-gradient(135deg, #FFB300, #FFCA28);
            color: #333;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-family: 'Open Sans', sans-serif;
            font-weight: 600;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease;
            margin-right: 10px;
        }
        .course-link-modern:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            background: linear-gradient(135deg, #FFA000, #FFB300);
            border: 1px solid #FFCA28;
        }
        .enroll-button-modern {
            display: inline-block;
            background: linear-gradient(135deg, #FFB300, #FFCA28);
            color: #333;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-family: 'Open Sans', sans-serif;
            font-weight: 600;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.3s ease;
            margin-top: 10px;
        }
        .enroll-button-modern:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            background: linear-gradient(135deg, #FFA000, #FFB300);
            border: 1px solid #FFCA28;
        }
        .insight-text {
            color: #333;
            font-size: 0.95rem;
            line-height: 1.6;
            margin-top: 1rem;
        }
        .result-text {
            font-weight: 700;
            color: #333;
            font-size: 0.95rem;
            line-height: 1.6;
            margin-top: 0.5rem;
        }
        .tips-list {
            list-style-type: disc;
            padding-left: 20px;
            margin: 0;
        }
        .tips-list li {
            margin-bottom: 0.75rem;
        }
        .tips-list strong {
            font-weight: 600;
        }
        .grid-card {
            min-height: 300px;
        }
        .badges-card {
            min-height: 350px;
        }
        .tips-card {
            min-height: 350px;
            overflow-y: auto;
        }
        .row.align-headers {
            display: flex;
            align-items: flex-start;
        }
        .row.main-grid {
            margin-bottom: 0;
        }
        .chart-empty-state {
            background: #F5F5F5;
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
            color: #666;
            font-size: 1rem;
            font-family: 'Open Sans', sans-serif;
        }
        .chart-empty-state::before {
            content: "\f201";
            font-family: "Font Awesome 6 Free";
            font-weight: 900;
            display: block;
            font-size: 2rem;
            color: #999;
            margin-bottom: 0.75rem;
        }
        .logo-container {
            text-align: center;
            margin-bottom: 2rem;
        }
        .logo-container img {
            max-width: 200px;
        }
        .welcome-info {
            font-weight: 700;
            color: #333;
            font-size: 1rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        @media (max-width: 600px) {
            .card-base {
                padding: 1rem;
                margin-bottom: 1rem;
            }
            .card-header-modern {
                font-size: 1.25rem;
                white-space: normal;
                padding: 0.75rem;
            }
            h3 {
                font-size: 1.25rem;
            }
            .subheading {
                font-size: 1rem;
            }
            .grid-card, .badges-card, .tips-card {
                min-height: auto;
            }
            .row.align-headers {
                display: block;
                flex-direction: column;
            }
        }
        @media (max-width: 400px) {
            .emoji {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Logo -->
        <div class="logo-container">
            <img src="{{ url_for('static', filename='img/ficore_logo.png') }}" alt="Ficore Africa Logo" class="img-fluid">
        </div>

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="alert-container my-3">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Main Grid -->
        <div class="row main-grid">
            <!-- Left Column (Wider) -->
            <div class="col-md-8">
                <!-- Welcome + Financial Health Score Card -->
                <div class="card-base grid-card badges-card">
                    <div class="card-header-modern">
                        <span class="emoji">🎉</span> {{ translations[language]['Welcome'] }}, {{ first_name }}!
                    </div>
                    <div class="card-body">
                        <p class="welcome-info">
                            {{ translations[language]['Email'] }}: {{ email }}<br>
                            Name: {{ first_name }} {{ last_name }}<br>
                            Score Insight: 
                            {% if health_score >= 75 %}
                                Strong Financial Health
                            {% elif health_score >= 50 %}
                                Stable Finances
                            {% elif health_score >= 25 %}
                                Financial Strain
                            {% else %}
                                Urgent Attention Needed
                            {% endif %}
                        </p>
                        <p class="subheading">{{ translations[language]['Your Financial Health Summary'] }}</p>
                        {% if personalized_message %}
                            <p><strong>{{ personalized_message }}</strong></p>
                        {% endif %}
                        <div class="section-divider-modern"></div>
                        <h3>⭐ {{ translations[language]['Your Financial Health Score'] }}</h3>
                        <p class="result-text">{{ health_score }}/100</p>
                        <p class="result-text">{{ translations[language]['Ranked'] }} #{{ rank }} {{ translations[language]['out of'] }} {{ total_users }} {{ translations[language]['users'] }}</p>
                        <p class="result-text">
                            {% if health_score >= 75 %}
                                {{ translations[language]['Strong Financial Health'] }}
                            {% elif health_score >= 50 %}
                                {{ translations[language]['Stable Finances'] }}
                            {% elif health_score >= 25 %}
                                {{ translations[language]['Financial Strain'] }}
                            {% else %}
                                {{ translations[language]['Urgent Attention Needed'] }}
                            {% endif %}
                        </p>
                    </div>
                </div>

                <!-- Score Breakdown Card -->
                <div class="card-base grid-card">
                    <div class="card-header-modern">
                        <span class="emoji">📊</span> {{ translations[language]['Score Breakdown'] }}
                    </div>
                    <div class="card-body">
                        {% if breakdown_plot %}
                            {{ breakdown_plot|safe }}
                        {% else %}
                            <div class="chart-empty-state">
                                {{ translations[language]['Chart Unavailable'] }}
                            </div>
                        {% endif %}
                        <p class="insight-text">
                            {{ translations[language]['Score Composition'] }}:
                            <ul>
                                <li><strong>{{ translations[language]['Cash Flow'] }}</strong>: {{ translations[language]['Cash Flow Description'] }}</li>
                                <li><strong>{{ translations[language]['Debt-to-Income Ratio'] }}</strong>: {{ translations[language]['Debt-to-Income Description'] }}</li>
                                <li><strong>{{ translations[language]['Debt Interest Burden'] }}</strong>: {{ translations[language]['Debt Interest Description'] }}</li>
                            </ul>
                            {% if health_score >= 75 %}
                                {{ translations[language]['Balanced Components'] }}
                            {% elif health_score >= 50 %}
                                {{ translations[language]['Components Need Attention'] }}
                            {% else %}
                                {{ translations[language]['Components Indicate Challenges'] }}
                            {% endif %}
                        </p>
                    </div>
                </div>
            </div>

            <!-- Right Column (Narrower) -->
            <div class="col-md-4">
                <!-- Badges + Recommended Learning Card -->
                <div class="card-base grid-card badges-card">
                    <div class="card-header-modern">
                        <span class="emoji">🏅</span> {{ translations[language]['Your Badges'] }}
                    </div>
                    <div class="card-body">
                        {% if badges %}
                            {% for badge in badges %}
                                <span class="badge-modern"><i class="fas fa-trophy"></i> {{ translations[language].get(badge, badge) }}</span>
                            {% endfor %}
                        {% else %}
                            <p>{{ translations[language]['No Badges Yet'] }}</p>
                        {% endif %}
                        <div class="section-divider-modern"></div>
                        <h3>📚 {{ translations[language]['Recommended Learning'] }}</h3>
                        <a href="{{ course_url }}" target="_blank" class="course-link-modern" aria-label="{{ translations[language]['Recommended Course'] }}: {{ course_title }}">
                            {{ course_title }}
                        </a>
                        <a href="{{ course_url }}" target="_blank" class="enroll-button-modern" aria-label="{{ translations[language]['Enroll in'] }} {{ course_title }}">
                            {{ translations[language]['Enroll Now'] }}
                        </a>
                    </div>
                </div>

                <!-- Quick Financial Tips Card -->
                <div class="card-base grid-card tips-card">
                    <div class="card-header-modern">
                        <span class="emoji">💡</span> {{ translations[language]['Quick Financial Tips'] }}
                    </div>
                    <div class="card-body">
                        <ul class="tips-list">
                            {% if health_score >= 75 %}
                                <li><strong>{{ translations[language]['Invest'] }}</strong>: {{ translations[language]['Invest Wisely'] }}</li>
                                <li><strong>{{ translations[language]['Scale'] }}</strong>: {{ translations[language]['Scale Smart'] }}</li>
                            {% elif health_score >= 50 %}
                                <li><strong>{{ translations[language]['Build'] }}</strong>: {{ translations[language]['Build Savings'] }}</li>
                                <li><strong>{{ translations[language]['Cut'] }}</strong>: {{ translations[language]['Cut Costs'] }}</li>
                            {% else %}
                                <li><strong>{{ translations[language]['Reduce'] }}</strong>: {{ translations[language]['Reduce Debt'] }}</li>
                                <li><strong>{{ translations[language]['Boost'] }}</strong>: {{ translations[language]['Boost Income'] }}</li>
                            {% endif %}
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <!-- How You Compare to Others Section -->
        <div class="row">
            <div class="col-12">
                <div class="card-base">
                    <div class="card-header-modern">
                        <span class="emoji">⚖️</span> {{ translations[language]['How You Compare'] }}
                    </div>
                    <div class="card-body">
                        {% if comparison_plot %}
                            {{ comparison_plot|safe }}
                        {% else %}
                            <div class="chart-empty-state">
                                {{ translations[language]['Chart Unavailable'] }}
                            </div>
                        {% endif %}
                        <p class="insight-text">
                            {{ translations[language]['Your Rank'] }} #{{ rank }} {{ translations[language]['out of'] }} {{ total_users }} {{ translations[language]['users'] }} {{ translations[language]['places you'] }}:
                            {% if rank <= total_users * 0.1 %}
                                {{ translations[language]['Top 10%'] }}
                            {% elif rank <= total_users * 0.3 %}
                                {{ translations[language]['Top 30%'] }}
                            {% elif rank <= total_users * 0.7 %}
                                {{ translations[language]['Middle Range'] }}
                            {% else %}
                                {{ translations[language]['Lower Range'] }}
                            {% endif %}
                            {{ translations[language]['Regular Submissions'] }}
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- What's Next Section -->
        <div class="row">
            <div class="col-12">
                <div class="card-base">
                    <div class="card-header-modern">
                        <span class="emoji">🔓</span> {{ translations[language]['Whats Next'] }}
                    </div>
                    <div class="card-body">
                        <div class="d-flex flex-wrap justify-content-center gap-2 mb-3">
                            <a href="{{ url_for('home') }}" class="btn btn-primary-modern">{{ translations[language]['Back to Home'] }}</a>
                            <a href="{{ FEEDBACK_FORM_URL }}" class="btn btn-secondary-modern">{{ translations[language]['Provide Feedback'] }}</a>
                            <a href="{{ WAITLIST_FORM_URL }}" class="btn btn-secondary-modern">{{ translations[language]['Join Waitlist'] }}</a>
                            <a href="{{ CONSULTANCY_FORM_URL }}" class="btn btn-secondary-modern">{{ translations[language]['Book Consultancy'] }}</a>
                        </div>
                        <p class="text-center">{{ translations[language]['Contact Us'] }} <a href="mailto:Ficoreafrica@outlook.com">Ficoreafrica@outlook.com</a> {{ translations[language]['for support'] }}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/bootstrap.bundle.min.js') }}"></script>
</body>
</html>
