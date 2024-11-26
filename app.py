import csv
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
import pickle
import numpy as np
import pandas as pd
from itsdangerous import URLSafeTimedSerializer, SignatureExpired


# Initialize Flask app and database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:sahi#3012@localhost/evUSERS'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'


# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sahithyamadala@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'ejql wlnb tixn sehv'         # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = 'sahithyamadala@gmail.com'

# Initialize Flask-Mail and SQLAlchemy
mail = Mail(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# User model for the database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    dob = db.Column(db.Date, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    password_reset_token = db.Column(db.String(256), nullable=True)
    
    def __repr__(self):
        return f'<User {self.name}>'

# Path to the CSV file
CSV_FILE = 'data/data.csv'

def read_csv_file():
    with open(CSV_FILE, newline='') as f:
        reader = csv.reader(f)
        data = list(reader)
    return data

# Load the trained model
model = pickle.load(open("model.pkl", "rb"))

# Load dataset to get vehicle-related data
data = pd.read_csv("data.csv")
vehicle_names = data['Make'].unique()

@app.route('/')
def loginpg():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        role = request.form.get('role')

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email format!', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter((User.email == email) | (User.phone == phone)).first()
        if existing_user:
            flash('Email or Phone number already registered.', 'error')
            return redirect(url_for('register'))

        try:
            dob = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format! Use YYYY-MM-DD.', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, phone=phone, dob=dob, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        # Send a welcome email
        send_welcome_email(email, name)

        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['user_role'] = new_user.role

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('registration.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_phone = request.form.get('email_or_phone')
        password = request.form.get('password')

        user = User.query.filter(
            (User.email == email_or_phone) | (User.phone == email_or_phone)
        ).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash(f'Welcome {user.name}! Login successful.', 'success')
            return redirect(url_for('index' if user.role != 'Driver' else 'driver'))
        else:
            flash('Invalid credentials.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/index')
def index():
    if 'user_id' not in session:
        flash('You must log in to access this page.', 'error')
        return redirect(url_for('login'))
    return render_template('index.html', user_name=session.get('user_name'))
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate a temporary password reset token (or use UUID or JWT for secure tokens)
            reset_token = generate_password_hash(f"{email}{datetime.now()}", method='pbkdf2:sha256')
            session['reset_token'] = reset_token  # Store it temporarily for demonstration purposes

            # Send password reset email
            try:
                msg = Message(
                    'Password Reset Request',
                    recipients=[email],
                    body=f"Hi {user.name},\n\nClick the link below to reset your password:\n"
                         f"http://localhost:5000/reset_password?token={reset_token}\n\n"
                         f"If you did not request a password reset, please ignore this email.\n\nBest regards,\nEV System Team"
                )
                mail.send(msg)
                flash('Password reset link sent to your email.', 'success')
            except Exception as e:
                print(f"Error sending email: {e}")
                flash('Error sending email. Please try again later.', 'error')
        else:
            flash('Email not registered.', 'error')

        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    reset_token = request.args.get('token')  
    if not reset_token:
        flash("Invalid password reset request.", "error")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash("Passwords do not match. Please try again.", "error")
            return render_template('reset_password.html', token=reset_token)

        hashed_password = generate_password_hash(new_password)
        user = User.query.filter_by(password_reset_token=reset_token).first()

        if user:
            user.password = hashed_password
            user.password_reset_token = None  # Clear the reset token after password change
            db.session.commit()
            flash("Your password has been successfully updated!", "success")
            return redirect(url_for('login')) 
        else:
            flash("Invalid or expired token.", "error")
            return redirect(url_for('forgot_password')) 

    return render_template('reset_password.html', token=reset_token)

@app.route('/driver', methods=['GET', 'POST'])
def driver():
    if request.method == 'POST':
        try:
            battery_percentage = float(request.form['battery'])
            model_id = int(request.form['model_id'])

            default_features_dict = {
                1: [7.4, 160, 425, 170, 330, 78, 4607, 1800, 1479, 2735, 2490, 496, 405, 0, 0, 1, 0, 0, 0, 1, 0],
                # Add more default features here...
            }

            if model_id not in default_features_dict:
                return render_template('predictFORdriver.html', prediction_text="Invalid model ID.")

            final_features = [battery_percentage] + default_features_dict[model_id]
            final_features = np.array(final_features).reshape(1, -1)
            prediction = model.predict(final_features)
            output = round(prediction[0], 2)
            return render_template('predictFORdriver.html', prediction_text=f'Predicted Range: {output} km')
        except Exception as e:
            return render_template('predictFORdriver.html', prediction_text=str(e))
    return render_template('predictFORdriver.html')

def send_welcome_email(email, name):
    try:
        msg = Message('Welcome to EV System', recipients=[email])
        msg.body = f"Hi {name},\n\nThank you for registering with us!\n\nBest regards,\nEV System Team"
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

@app.route('/distribution')
def distribution():
    return render_template('distribution.html')

@app.route('/status')
def status():
    return render_template('status.html')

@app.route('/pie')
def pie():
    return render_template('pie.html')

@app.route('/relation')
def relation():
    return render_template('relation.html')

@app.route('/dataset')
def dataset():
    # Read data from CSV file
    data = []
    with open('data/data.csv', newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        header = next(csvreader)  # Read the header row
        for row in csvreader:
            data.append(row)
    return render_template('dataset.html', header=header, data=data)


@app.route('/data', methods=['GET'])
def get_data():
    action = request.args.get('action', 'headers')

    # Read CSV data
    data = read_csv_file()

    if action == 'headers':
        headers = data[0]  # First row is headers
        return jsonify(headers)
    
    elif action == 'column':
        selected_column = request.args.get('column')
        headers = data[0]

        # Check if the column exists
        if selected_column not in headers:
            return jsonify({'error': 'Invalid column', 'headers': headers}), 400
        
        column_index = headers.index(selected_column)
        column_data = [row[column_index] for row in data[1:]]  # Exclude header row

        return jsonify(column_data)
    
    elif action == 'pieData':
        selected_column = request.args.get('column')
        headers = data[0]

        if selected_column not in headers:
            return jsonify({'error': 'Invalid column', 'headers': headers}), 400
        
        column_index = headers.index(selected_column)
        column_data = [row[column_index] for row in data[1:]]
        
        # Count occurrences for pie chart
        value_counts = {}
        for value in column_data:
            value_counts[value] = value_counts.get(value, 0) + 1
        
        return jsonify(value_counts)
    

        
    elif action == 'conditionalCounts':
        selected_column = request.args.get('column')
        headers = data[0]

        # Ensure columns exist
        try:
            status_index = headers.index('Vehicle Status')
            selected_index = headers.index(selected_column)
        except ValueError:
            return jsonify({'error': 'Invalid column'}), 400
        
        counts = {}

        for row in data[1:]:
            status = row[status_index]
            value = row[selected_index]

            # Skip invalid rows
            if status not in ['0', '1'] or not value:
                continue
            
            if value not in counts:
                counts[value] = {'0': 0, '1': 0}
            
            counts[value][status] += 1

        return jsonify(counts)
    
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        try:
            battery_percentage = float(request.form['battery'])
            model_id = int(request.form['model_id'])

            default_features_dict = {
                1: [7.4, 160, 425, 170, 330, 78, 4607, 1800, 1479, 2735, 2490, 496, 405, 0, 0, 1, 0, 0, 0, 1, 0],
                2: [5.7, 190, 470, 250, 430, 83, 4783, 1852, 1448, 2856, 2605, 555, 470, 0, 1, 0, 0, 0, 0, 0, 1],
                3: [7.4, 160, 425, 170, 330, 78, 4607, 1800, 1479, 2735, 2490, 496, 405, 0, 0, 1, 0, 0, 0, 1, 0],
                4: [3.3, 261, 460, 377, 660, 82, 4694, 1849, 1443, 2875, 2232, 388, 561, 1, 0, 0, 0, 0, 1, 0, 0],
                5: [7.4, 160, 425, 170, 330, 78, 4607, 1800, 1479, 2735, 2490, 496, 405, 0, 0, 1, 0, 0, 0, 1, 0],
            }

            # Validate model ID
            if model_id not in default_features_dict:
                return render_template('predict.html', prediction_text="Invalid model ID.")

            # Create feature vector
            default_features = default_features_dict[model_id]
            final_features = [battery_percentage] + default_features
            final_features = np.array(final_features).reshape(1, -1)

            # Validate feature vector length
            assert len(final_features[0]) == 22, f"Feature vector size mismatch! Expected 22 but got {len(final_features[0])}"

            # Predict and return the result
            prediction = model.predict(final_features)
            output = round(prediction[0], 2)
            return render_template('predict.html', prediction_text=f'Predicted Range: {output} km')

        except ValueError:
            return render_template('predict.html', prediction_text="Invalid input. Please enter a valid number for battery percentage.")
        except AssertionError as e:
            return render_template('predict.html', prediction_text=f"Error: {str(e)}")
    else:
        return render_template('predict.html', prediction_text="")






if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create all database tables if they do not exist
    app.run(debug=True)








