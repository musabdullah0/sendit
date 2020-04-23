import os
import re

import phonenumbers
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template, session, url_for, redirect
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from twilio.rest import Client
from wtforms import ValidationError
from wtforms.fields import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from authlib.integrations.flask_client import OAuth


load_dotenv()

app = Flask(__name__)
Bootstrap(app)


app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32)
app.config['UPLOAD_FOLDER'] = os.path.dirname(app.instance_path) + '/uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_ACCOUNT_TOKEN'] = os.getenv('TWILIO_ACCOUNT_TOKEN')
app.config['NGROK_URL'] = 'http://aff0e1ff.ngrok.io'

# twilio client setup
app.client = Client(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_ACCOUNT_TOKEN']
)

# oAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # This is only needed if using openId to fetch user info
    client_kwargs={'scope': 'openid email profile'},
)


class UploadForm(FlaskForm):
    number = StringField('Phone Number', validators=[Length(min=10, max=15)])
    file = FileField('File', validators=[FileAllowed(['png', 'jpeg', 'gif'])])

    def validate_number(self, number):
        try:
            if re.search("[a-zA-Z]", number.data):
                raise ValueError()
            num = number.data.replace('-', '')
            num = '+1' + num if len(num) == 10 else num
            p = phonenumbers.parse(num)
            if not phonenumbers.is_valid_number(p):
                raise ValueError()
        except (phonenumbers.phonenumberutil.NumberParseException, ValueError):
            raise ValidationError('Invalid phone number')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/login')
def login():
    google = oauth.create_client('google')  # create the google oauth client
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/authorize')
def authorize():
    google = oauth.create_client('google')  # create the google oauth client
    token = google.authorize_access_token()  # Access token from google (needed to get user info)
    resp = google.get('userinfo')  # userinfo contains stuff u specified in the scope
    user_info = resp.json()
    user = oauth.google.userinfo()  # uses openid endpoint to fetch user info
    # Here you use the profile/user data that you got and query your database find/register the user
    # and set ur own data in the session not the profile from google
    session['profile'] = user_info
    session.permanent = True  # make the session permanent so it keeps existing after browser gets closed
    return redirect('/')


@app.route('/logout')
def logout():
    for key in list(session.keys()):
        session.pop(key)
    return redirect('/')


def is_logged_in():
    user = dict(session).get('profile', None)
    return user


# how would I serve the image publicly when deployed to heroku?
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/', methods=['GET', 'POST'])
def index():
    if not is_logged_in():
        return redirect('/login')
    form = UploadForm()
    if form.validate_on_submit():
        print('validated')
        file = request.files.get('file')
        number = request.form.get('number')
        save_and_send(file, number)
        return render_template('sent.html', filename=file.filename, number=number)

    user = dict(session).get('profile', None)
    return render_template('send.html', form=form, user=user)


def save_and_send(file, to):
    filename = file.filename.replace(' ', '_')
    filename = filename.lower()
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    img_url = app.config['NGROK_URL'] + f'/uploads/{filename}'
    print(f'sending {filename} to {to}')
    app.client.messages.create(
                body='dank meme sent from flask app',
                media_url=img_url,
                from_='+14243250993',
                to=to
            )


if __name__ == '__main__':
    app.run(debug=True)

'''
    REMEMBER
    - run `~/ngrok http 5000` to get the url
    - replace app.config['NGROK_URL'] with it
    
    TODO
    - check for errors from twilio and show that error on a new html page
    - gotta add phone number to twilio
    - add drop zone instead of file chooser
    - figure out how to deploy this thing
    - add donate button
    
    PROBLEM
    - can't programmatically verify numbers on twilio with free tier
    - unless I get money, can't continue project rip
'''