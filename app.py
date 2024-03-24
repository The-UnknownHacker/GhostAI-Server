from flask import Flask, render_template, request, jsonify, send_file, Response, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from io import BytesIO
from training_data import convo
from model_utils import safety_settings_default
import google.generativeai as genai
from flask_pymongo import PyMongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import requests
from PIL import Image, UnidentifiedImageError
import os
import io
import tempfile

api_key = "AIzaSyABntLwQVD7Ql7GxSHJN1ZPyMpz2yyyFRg"  # Define the API key; needs to be changed if you want to use it


API_URL = "https://frightened-dove-turtleneck-shirt.cyclic.app/proxy/https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
HEADERS = {"Authorization": "Bearer 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"}

generation_config = {  # Redefine the generation config
    "temperature": 1.0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 200,
}


app = Flask(__name__)
genai.configure(api_key=api_key)
app.config['API_KEY'] = api_key  # Set a global variable to assign API key
app.config['SAFETY_SETTINGS'] = safety_settings_default  # Set the safety settings to the default ones
app.secret_key = 'secret_key'
app.lazy_loading = False
mongo_url = 'mongodb+srv://ghostai:ghostai@ghostai.4bni5mt.mongodb.net/your_database_name?retryWrites=true&w=majority&appName=GhostAI'
app.config['MONGO_URI'] = mongo_url
mongo = PyMongo(app)  # Move this line to the global scope
client = MongoClient(mongo_url, server_api=ServerApi('1'))



with app.app_context():
    mongo.init_app(app)


class User(UserMixin):
    pass

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'
invalid_request = 0

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'username': user_id})

    if user_data:
        user = User()
        user.id = user_id

        # Check if the user is pro
        if user_data.get('pro', 'false') == 'true':
            user.pro = True
        else:
            user.pro = False

        return user

    return None



app.config['API_KEY'] = "AIzaSyABntLwQVD7Ql7GxSHJN1ZPyMpz2yyyFRg"  # Replace with Your Own API Key
app.config['SAFETY_SETTINGS'] = safety_settings_default



@app.route('/')
def home():
    return render_template('index.html') # Change to site_down.html for maintenance mode


@app.route('/talk')
def talk():
    return render_template('page_down.html')

@app.route('/privacy')
def privacy():
    return render_template('Privacy.html')

@app.route('/settings')
def settings():
    return render_template('settings.html', default_api_key=app.config['API_KEY'])

@app.route('/save_api_key', methods=['POST'])
def save_api_key():
    api_key = request.form.get('api_key')

    if api_key != app.config['API_KEY']:
        app.config['API_KEY'] = api_key
        app.config['SAFETY_SETTINGS'] = safety_settings_default
        return jsonify({'message': 'API Key saved successfully'})
    else:
        return jsonify({'message': 'Please enter a different API Key'})

@app.route('/send_message', methods=['POST'])
def send_message():
    user_input = request.form.get('user_input')
    response = generate_response(user_input)
    return jsonify({'response': response})

@app.route('/download')
def download_page():
    return render_template('downloads.html')

def generate_response(user_input):
    response = convo.send_message(user_input).text
    print()
    print()
    print(f'User Input: {user_input}')
    print(f'AI Response: {response}')
    print()
    print()
    return response


@app.route('/success')
def success():
    return render_template('success.html')

# New login route
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username and password match an existing user in MongoDB
        user = mongo.db.users.find_one({'username': username, 'password': password})
        if user:
            user_obj = User()
            user_obj.id = username

            # Check if the user is pro
            if user.get('pro', 'false') == 'true':
                user_obj.pro = True
            else:
                user_obj.pro = False

            login_user(user_obj)
            return redirect(url_for('success'))
        else:
            return render_template('login.html', error='Incorrect Username Or Password', invalid_request=invalid_request + 1)

    return render_template('login.html')




@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username is already taken in MongoDB
        existing_user = mongo.db.users.find_one({'username': username})
        if existing_user:
            return render_template('signup.html', error='Username already taken')

        # Store the user data in MongoDB
        mongo.db.users.insert_one({'username': username, 'password': password, 'pro': 'false'})

        # Redirect to the success page
        return redirect(url_for('signup_success'))

    # Render the signup form template for GET requests
    return render_template('signup.html')




@app.route('/signup_success')
def signup_success():
    return render_template('signup_success.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/upgrade')
def upgrade():
    return render_template('upgrade.html')

def query(payload):
    response = requests.post(API_URL, headers=HEADERS, json=payload)
    return response.content


# Protected img route

@app.route('/img', methods=['GET', 'POST'])
def generate_image():
    # Check if the user is authenticated and has "pro" status
    if current_user.is_authenticated and current_user.pro:
        if request.method == 'POST':
            input_prompt = request.form.get("prompt")

            if not input_prompt:
                return "No prompt provided", 400

            try:
                # Call your existing function to query the AI model
                image_bytes = query({"inputs": input_prompt})
                image = Image.open(io.BytesIO(image_bytes))

                # Ensure the /img directory exists
                img_dir = os.path.join(app.root_path, 'img')
                os.makedirs(img_dir, exist_ok=True)

                # Create a unique file name for the image in the /img directory
                fd, temp_file_path = tempfile.mkstemp(suffix='.png', dir=img_dir)
                os.close(fd)  # Close the file descriptor

                # Save the image to the file
                image.save(temp_file_path, format='PNG')

                # Generate the path relative to the Flask app for serving
                relative_path = os.path.relpath(temp_file_path, start=app.root_path)

                return send_file(relative_path, mimetype='image/png')

            except UnidentifiedImageError:
                error_message = "Sorry, we couldn't generate the image. Please try again later."
                return render_template("img.html", error_message=error_message)

        # If it's a GET request, just render the form
        return render_template('img.html')
    else:
        # Handle non-pro user access (optional: redirect to a different page)
        return render_template('upgrade.html', error="You need to be a pro user to access this feature.")



"""
@app.route('/img', methods=['GET', 'POST'])
def img():
    return render_template('page_work.html')
"""



if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False, port=5000)
