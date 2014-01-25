import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from contextlib import closing
import time
from flask.ext.login import LoginManager, UserMixin, current_user
from flaskext.browserid import BrowserID
from flask.ext.sqlalchemy import SQLAlchemy
from flaskext.gravatar import Gravatar
from pprint import pprint
from hashlib import md5
from datetime import datetime
import urllib2
import json

## SETUP
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/flaskr.db'
db = SQLAlchemy(app)
app.config.from_object(__name__)

app.config['BROWSERID_LOGIN_URL'] = "/login"
app.config['BROWSERID_LOGOUT_URL'] = "/logout"
app.config['SECRET_KEY'] = "deterministic"
app.config['TESTING'] = True

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.UnicodeText, unique=True)
    firstname = db.Column(db.Unicode(40))
    lastname = db.Column(db.Unicode(40))
    date_register = db.Column(db.Integer)
    address = db.Column(db.Unicode(1000))
    city = db.Column(db.Unicode(200))
    state = db.Column(db.Unicode(100))
    country = db.Column(db.Unicode(50))
    zipcode = db.Column(db.Integer)
    bio = db.Column(db.Text)
    facebook = db.Column(db.Unicode(1000))
    twitter = db.Column(db.Unicode(1000))
    website = db.Column(db.Unicode(1000))
    image = db.Column(db.LargeBinary)

    def __init__(self, email, firstname=None, lastname=None, date_register=None, bio=None, address=None, city=None, 
                    state=None, country=None, zipcode=None, facebook=None, twitter=None, website=None, image=None):
        self.email = email
        self.firstname = firstname
        self.lastname = lastname
        self.date_register = time.time()
        self.bio = bio
        self.address = address
        self.city = city
        self.state = state
        self.country = country
        self.zipcode = zipcode
        self.facebook = facebook
        self.twitter = twitter
        self.website = website
        self.image = image

    def __repr__(self):
        return '<User %r>' % self.email

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

### Login Functions ###
def get_user_by_id(id):
    """
    Given a unicode ID, returns the user that matches it.
    """
    return User.query.get(id)

def create_browserid_user(kwargs):
    """
    Takes browserid response and creates a user.
    """
    if kwargs['status'] == 'okay':
        user = User(kwargs['email'])
        db.session.add(user)
        db.session.commit()
        print "create_browserid_user - " + str(type(user)) + " - " + str(user)
        return user
    else:
        return None

def get_user(kwargs):
    """
    Given the response from BrowserID, finds or creates a user.
    If a user can neither be found nor created, returns None.
    """
    u = User.query.filter(db.or_(
        User.id == kwargs.get('id'),
        User.email == kwargs.get('email')
    )).first()
    if u is None: # user didn't exist in db
        return create_browserid_user(kwargs)
    return u

login_manager = LoginManager()
login_manager.user_loader(get_user_by_id)
login_manager.init_app(app)

browserid = BrowserID()
browserid.user_loader(get_user)
browserid.init_app(app)

## Sunlight Labs Setup ##
apiKey = "apikey=578f15b9d3a44ebb8c829860d609bba8"
apiAddr = "http://congress.api.sunlightfoundation.com/"
leglookup = "legislators/locate"

## Useful Dictionaries ##
day_suffix = {'1': 'st', '2': 'nd', '3': 'rd', '4': 'th', '5': 'th', '6': 'th', '7': 'th', '8': 'th', '9': 'th', '0': 'th'}
month_dict = {'01': 'Jan', '02': 'Feb', '03': 'March', '04': 'April', '05': 'May', '06': 'June', '07': 'July', '08': 'Aug', '09': 'Sep', 
        '10': 'Oct', '11': 'Nov', '12': 'Dec',}

def get_lat_long(remote_addr):
    #remote_addr = "162.210.196.172"
    req = urllib2.urlopen("http://freegeoip.net/json/" + remote_addr)
    return json.loads(req.read())

def add_images(data):
    for member in data['results']:
        member['img'] = "http://bioguide.congress.gov/bioguide/photo/" + member["bioguide_id"][:1] + \
                            "/" + member["bioguide_id"] + ".jpg"
    return data

def timestamp_prettify(timestamp):
    year, month, day = timestamp.split("-")
    new = month_dict[month] + " "
    if day[0] == "0": new += day[1]
    else: new += day
    new += day_suffix[day[1]] + ", " + year
    return new


### Routing ###
@app.route('/')
def home():
    if current_user.is_authenticated():
        return render_template('dashboard.html')
    #lat_long = get_lat_long(request.remote_addr)
    #print "Lat: " + str(lat_long['latitude']) + " - Long: " + str(lat_long['longitude'])
    #print lat_long
    return render_template('index.html')

@app.route('/zip', methods=['GET', 'POST'])
def zip():
    if current_user.is_authenticated():
        if request.method == 'POST':
            req = apiAddr + leglookup + "?" + apiKey + "&zip=" + request.form.get('zipcode')
            req = urllib2.urlopen(req).read()
            data = json.loads(req)
            data = add_images(data)
        return render_template('zip.html', data=data, timestamp_prettify=timestamp_prettify)
    return render_template('index.html')

@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if current_user.is_authenticated():
        email = md5(current_user.email).hexdigest()
        if request.method == 'POST':
            user = get_user({"email": current_user.email})
            id = user.id
            user = User.query.get(id)
            if request.form.get('firstname') != u'': user.firstname = request.form.get('firstname')
            if request.form.get('lastname') != u'': user.lastname = request.form.get('lastname')
            if request.form.get('bio') != u'': user.bio = request.form.get('bio')
            if request.form.get('address') != u'': user.address = request.form.get('address')
            if request.form.get('city') != u'': user.city = request.form.get('city')
            if request.form.get('state') != u'': user.state = request.form.get('state')
            if request.form.get('country') != u'': user.country = request.form.get('country')
            if request.form.get('zipcode') != u'': user.zipcode = request.form.get('zipcode')
            if request.form.get('facebook') != u'': user.facebook = request.form.get('facebook')
            if request.form.get('twitter') != u'': user.twitter = request.form.get('twitter')
            if request.form.get('website') != u'': user.website = request.form.get('website')
            if request.form.get('image') != u'': user.image = request.form.get('image')
            try:
                db.session.commit()
            except:
                return render_template('editprofile.html', alert_failure=True, email=email)
            return render_template('editprofile.html', alert_success=True, email=email)
        return render_template('editprofile.html', email=email)
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if current_user.is_authenticated():
        if request.method == 'POST':
            user = get_user({"email": current_user.email})
            id = user.id
            user = User.query.get(id)
            if request.form.get('email') != u'': user.email = request.form.get('email')
            try:
                db.session.commit()
            except:
                return render_template('settings.html', alert_failure=True)
            return render_template('settings.html', alert_success=True)
        return render_template('settings.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/browse')
def browse():
    if current_user.is_authenticated():
        return render_template('browse.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/votingrecord')
def votingrecord():
    if current_user.is_authenticated():
        return render_template('votingrecord.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/vote')
def vote():
    if current_user.is_authenticated():
        return render_template('vote.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/compatibility')
def compatibility():
    if current_user.is_authenticated():
        return render_template('compatibility.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/blog')
def blog():
    if current_user.is_authenticated():
        return render_template('blog.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/profile')
def profile():
    if current_user.is_authenticated():
        return render_template('profile.html', date_register = datetime.fromtimestamp(int(current_user.date_register)).strftime('%m/%d/%Y at %H:%M:%S'))
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

### Admin Tools ###
@app.route('/show_db')
def show_db():
    users = []
    for user in db.session.query(User):
        users.append(dict(id=user.id, email=user.email, fisrtname=user.firstname, lastname=user.lastname, date_register=user.date_register))
    return render_template('show_db.html', users=users)


if __name__ == '__main__':
    app.run(host='0.0.0.0')