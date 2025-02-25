from flask import Flask, render_template, url_for, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
import tensorflow as tf
from PIL import Image
import numpy as np
import io

app = Flask(__name__)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            raise ValidationError('That username already exists. Please choose a different one.')

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')

# Load the TensorFlow model
model = tf.saved_model.load('model')

def preprocess_image(image):
    image = image.resize((224, 224))
    image = np.array(image) / 255.0
    image = image.astype('float32')
    return image

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        # Get the image file from the form
        image_file = request.files['image_file']
        # Read the image file
        image = Image.open(io.BytesIO(image_file.read()))
        # Preprocess the image
        image = preprocess_image(image)
        # Make prediction
        infer = model.signatures['serving_default']
        prediction = infer(tf.constant([image], dtype=tf.float32))
        predicted_probabilities = prediction['dense_1'].numpy()[0]
        predicted_class = np.argmax(predicted_probabilities)
        prediction_text = f'Hello, {current_user.username}, you are diabetic, visit to nearest hospital.' if predicted_class == 1 else f'Hello, {current_user.username}, you are not diabetic.'
        return render_template('result.html', prediction_text=prediction_text)
    except Exception as e:
        return render_template('result.html', prediction_text=f'Error: {str(e)}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('home'))
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

if __name__ == "__main__":
    app.run(debug=True)
