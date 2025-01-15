from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
import bcrypt
from flask_wtf.csrf import CSRFError
from bson.objectid import ObjectId
from config.logging import setup_logging, log_activity

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['MONGO_URI'] = os.environ.get('DATABASE_URL', 'mongodb://localhost:27017/quicksnatch')
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

# Initialize logging
activity_logger = setup_logging(app)

# Time formatting functions
def format_time_delta(start_time, end_time):
    if not start_time or not end_time:
        return "N/A"
    
    delta = end_time - start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)

def format_datetime(dt):
    if not dt:
        return "N/A"
    local_tz = pytz.timezone('Asia/Kolkata')  # Use your local timezone
    local_dt = dt.astimezone(local_tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")

# Add template functions
app.jinja_env.globals.update(
    format_time_delta=format_time_delta,
    format_datetime=format_datetime
)

# Initialize MongoDB
mongo = PyMongo(app)

# Initialize Login Manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['_id']
        self.team_name = user_data['team_name']
        self.current_level = user_data.get('current_level', 1)
        self.is_admin = user_data.get('is_admin', False)
        self.members = user_data.get('members', [])
        self.start_time = user_data.get('start_time')
        self.last_submission = user_data.get('last_submission')

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# Challenge answers
ANSWERS = {
    1: "flag{quick_basics}",
    2: "flag{chmod_master}",
    3: "flag{grep_master_123}",
    4: "flag{process_hunter}",
    5: "flag{network_ninja}",
    6: "flag{bash_wizard}",
    7: "flag{archive_explorer}",
    8: "flag{system_stalker}",
    9: "flag{cron_master}",
    10: "flag{ultimate_champion}"
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        password = request.form.get('password')
        team = mongo.db.users.find_one({'team_name': team_name})
        
        if team and bcrypt.checkpw(password.encode('utf-8'), team['password']):
            user = User(team)
            login_user(user)
            
            # Set start time if first login
            if not team.get('start_time'):
                mongo.db.users.update_one(
                    {'_id': team['_id']},
                    {'$set': {'start_time': datetime.now(pytz.UTC)}}
                )
            
            log_activity(activity_logger, team_name, 'LOGIN', status='success')
            return redirect(url_for('challenge', level=user.current_level))
        
        log_activity(activity_logger, team_name, 'LOGIN', status='failed')
        flash('Invalid team name or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        password = request.form.get('password')
        
        # Check if team name already exists
        if mongo.db.users.find_one({'team_name': team_name}):
            flash('Team name already exists')
            return redirect(url_for('register'))
        
        # Get team members info
        members = []
        for i in range(1, 3):  # 2 members
            member = {
                'name': request.form.get(f'member_name_{i}'),
                'email': request.form.get(f'member_email_{i}'),
                'phone': request.form.get(f'member_phone_{i}')
            }
            # Validate ADYPU email
            if not member['email'].endswith('@adypu.edu.in'):
                flash(f'Member {i} must use an ADYPU email address')
                return redirect(url_for('register'))
            members.append(member)
        
        # Create new team
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        team = {
            'team_name': team_name,
            'password': hashed,
            'members': members,
            'current_level': 1,
            'start_time': None,
            'last_submission': None,
            'created_at': datetime.now(pytz.UTC)
        }
        
        mongo.db.users.insert_one(team)
        flash('Team registered successfully! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/challenge/<int:level>', methods=['GET', 'POST'])
@login_required
def challenge(level):
    if level > current_user.current_level:
        flash('You must complete previous levels first!')
        return redirect(url_for('challenge', level=current_user.current_level))
    
    if request.method == 'POST':
        answer = request.form.get('answer')
        if answer == ANSWERS.get(level):
            # Record submission
            mongo.db.submissions.insert_one({
                'user_id': ObjectId(current_user.id),
                'level': level,
                'submitted_at': datetime.now(pytz.UTC),
                'is_correct': True
            })
            
            # Update user level if completed current level
            if level == current_user.current_level:
                mongo.db.users.update_one(
                    {'_id': ObjectId(current_user.id)},
                    {
                        '$inc': {'current_level': 1},
                        '$set': {'last_submission': datetime.now(pytz.UTC)}
                    }
                )
            
            log_activity(activity_logger, current_user.team_name, 'SUBMIT', level=level, status='success')
            flash('Correct! Moving to next level.')
            return redirect(url_for('challenge', level=level+1))
        else:
            mongo.db.submissions.insert_one({
                'user_id': ObjectId(current_user.id),
                'level': level,
                'submitted_at': datetime.now(pytz.UTC),
                'is_correct': False
            })
            log_activity(activity_logger, current_user.team_name, 'SUBMIT', level=level, status='failed')
            flash('Incorrect answer. Try again!')
    
    return render_template(f'challenges/level_{level}.html')

@app.route('/leaderboard')
def leaderboard():
    # Get all users and sort by level and time taken
    users = list(mongo.db.users.find(
        {},
        {
            'team_name': 1,
            'current_level': 1,
            'start_time': 1,
            'last_submission': 1
        }
    ))
    
    # Sort users by level and time taken
    def sort_key(user):
        level = user.get('current_level', 1)
        if not user.get('start_time') or not user.get('last_submission'):
            return (-level, float('inf'))
        time_taken = (user['last_submission'] - user['start_time']).total_seconds()
        return (-level, time_taken)
    
    users.sort(key=sort_key)
    return render_template('leaderboard.html', users=users)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/logs')
@login_required
def view_logs():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('index'))
    
    # Read activity logs
    activity_logs = []
    try:
        with open('logs/activity.log', 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    time = ' '.join(parts[0:2])
                    info = ' '.join(parts[2:]).split()
                    log_entry = {
                        'time': time,
                        'user': info[0].split(':')[1],
                        'action': info[1].split(':')[1],
                        'level': info[2].split(':')[1],
                        'status': info[3].split(':')[1]
                    }
                    activity_logs.append(log_entry)
    except FileNotFoundError:
        activity_logs = []
    
    # Read server logs
    try:
        with open('logs/quicksnatch.log', 'r') as f:
            server_logs = f.readlines()[-100:]  # Last 100 lines
    except FileNotFoundError:
        server_logs = []
    
    return render_template('logs.html', activity_logs=activity_logs, server_logs=server_logs)

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net"
    return response

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('errors/csrf.html'), 400

if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'development')
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 7771))
    
    # Database initialization and cleanup
    try:
        # Drop existing index if it exists
        mongo.db.users.drop_index('team_name_1')
    except:
        pass  # Index might not exist
    
    # Remove documents with null team_names
    mongo.db.users.delete_many({'team_name': None})
    
    # Create new unique index
    mongo.db.users.create_index('team_name', unique=True, sparse=True)
    
    # Production configurations
    if env == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True
    
    app.run(host=host, port=port, debug=env == 'development')
