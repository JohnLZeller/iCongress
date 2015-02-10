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
    firstvisit = db.Column(db.Boolean, default=True)

    def __init__(self, email, firstname=None, lastname=None, date_register=None, bio=None, address=None, city=None, 
                    state=None, country=None, zipcode=None, facebook=None, twitter=None, website=None):
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

    def __repr__(self):
        return '<User %r>' % self.email

class Vote(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer)
    legid = db.Column(db.Integer)
    vote = db.Column(db.Boolean) # True is Yes
    date = db.Column(db.Integer)

    def __init__(self, userid, legid, vote):
        self.userid = userid
        self.legid = legid
        self.decision = decision

    def __repr__(self):
        return '<Vote %r>' % self.id

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

## GovTrack Setup ##
govAddr = "https://www.govtrack.us/api/v2/"
currentMocs = "role?current=true&limit=600"
specificMoc = "person/"
specificBill = "bill/"
recentActiveBills = "bill/?order_by=-current_status_date"

## Useful Dictionaries ##
day_suffix = {'1': 'st', '2': 'nd', '3': 'rd', '4': 'th', '5': 'th', '6': 'th', '7': 'th', '8': 'th', '9': 'th', '0': 'th'}
month_dict = {'01': 'Jan', '02': 'Feb', '03': 'March', '04': 'April', '05': 'May', '06': 'June', '07': 'July', '08': 'Aug', '09': 'Sep', 
        '10': 'Oct', '11': 'Nov', '12': 'Dec',}

def get_lat_long(remote_addr):
    #remote_addr = "162.210.196.172"
    req = urllib2.urlopen("http://freegeoip.net/json/" + remote_addr)
    return json.loads(req.read())

def add_images(mocs):
    for member in mocs:
        member['img'] = moc_image(member)
    return mocs

def moc_image(member):
    if member.get('person'):
        bioguideid = member['person']['bioguideid']
    elif member.get('bioguideid'):
        bioguideid = member['bioguideid']

    return "http://bioguide.congress.gov/bioguide/photo/" + bioguideid[:1] + \
                            "/" + bioguideid + ".jpg"

def timestamp_prettify(timestamp):
    if timestamp is None:
        return None
    year, month, day = timestamp.split("-")
    new = month_dict[month] + " "
    if day[0] == "0": new += day[1]
    else: new += day
    new += day_suffix[day[1]] + ", " + year
    return new

def all_mocs():
    # TODO: When url request fails, don't error out
    reqall = govAddr + currentMocs
    reqall = urllib2.urlopen(reqall).read()
    dataall = json.loads(reqall)
    mocs = dataall['objects']
    mocs = add_images(mocs)

    for moc in mocs:
        moc['titlename'] = moc['person']['name'].split(' ')[0] + ' ' + moc['person']['firstname']
        if moc['person']['middlename']:
            moc['titlename'] += ' ' + moc['person']['middlename']
        moc['titlename'] += ' ' + moc['person']['lastname']
    # Each MoC has these keys
    # [u'senator_rank', u'congress_numbers', u'id', u'startdate', u'senator_class_label', 
    # u'district', u'title', u'title_long', u'current', u'state', u'party', u'leadership_title', 
    # u'website', u'description', u'phone', u'role_type', u'role_type_label', u'enddate', 
    # u'senator_rank_label', u'person', u'caucus', u'senator_class']

    return mocs

def local_mocs():
    # TODO: When url request fails, don't error out
    req = apiAddr + leglookup + "?" + apiKey + "&zip=" + unicode(current_user.zipcode)
    req = urllib2.urlopen(req).read()
    lmocs = json.loads(req)['results']

    # Grab mocs from govtrack
    for i, lmoc in enumerate(lmocs):
        reqlmoc = govAddr + specificMoc + lmoc['govtrack_id']
        reqlmoc = urllib2.urlopen(reqlmoc).read()
        reqlmoc = json.loads(reqlmoc)
        lmocs[i] = reqlmoc

        # Add standard keys expected by congress badge template
        lmocs[i]['person'] = {'bioguideid': lmocs[i]['bioguideid']}
        current_role = lmocs[i]['roles'][-1]
        lmocs[i]['party'] = current_role['party']
        lmocs[i]['startdate'] = current_role['startdate']
        lmocs[i]['enddate'] = current_role['enddate']
        lmocs[i]['district'] = current_role['district']
        lmocs[i]['state'] = current_role['state']
        lmocs[i]['senator_rank_label'] = current_role.get('senator_rank')
        if lmocs[i]['senator_rank_label']:
            lmocs[i]['senator_rank_label'] = lmocs[i]['senator_rank_label'].title()

        # Add titlename key
        lmocs[i]['titlename'] = lmocs[i]['name'].split(' ')[0] + ' ' + lmocs[i]['firstname']
        if lmocs[i]['middlename']:
            lmocs[i]['titlename'] += ' ' + lmocs[i]['middlename']
        lmocs[i]['titlename'] += ' ' + lmocs[i]['lastname']

    lmocs = add_images(lmocs)
    
    return lmocs

def specific_moc(govtrack_id):
    # Grabs from /person, which has a different format than /role
    reqlmoc = govAddr + specificMoc + str(govtrack_id)
    reqlmoc = urllib2.urlopen(reqlmoc).read()
    reqlmoc = json.loads(reqlmoc)
    moc = reqlmoc

    # Add standard keys expected by congress badge template
    moc['person'] = {'bioguideid': moc['bioguideid']}
    current_role = moc['roles'][-1]
    moc['party'] = current_role['party']
    moc['startdate'] = current_role['startdate']
    moc['enddate'] = current_role['enddate']
    moc['district'] = current_role['district']
    moc['state'] = current_role['state']
    moc['senator_rank_label'] = current_role.get('senator_rank')
    if moc['senator_rank_label']:
        moc['senator_rank_label'] = moc['senator_rank_label'].title()

    # Add titlename key
    moc['titlename'] = moc['name'].split(' ')[0] + ' ' + moc['firstname']
    if moc['middlename']:
        moc['titlename'] += ' ' + moc['middlename']
    moc['titlename'] += ' ' + moc['lastname']

    moc['img'] = moc_image(moc)
    
    return moc

def voting_history():
    user = get_user({"email": current_user.email})
    votes = Vote.query.filter(
                Vote.userid == user.id
            ).all()
    for vote in votes:
        vote["legislation"] = legislation_info(vote)
    return votes

def legislation_info(vote):
    # TODO: Grab real info
    info = {'status': None,
            'title': None,
            'introduced_on': None,
            'official_votes_for': None,
            'official_votes_against': None,
            'votes_for': None,
            'votes_against': None,
            'passed': None,
            'link': None}
    return info

def congressional_legislation(bill_id=None):
    # TODO: When url request fails, don't error out
    req = govAddr
    if bill_id:
        req += specificBill + bill_id
    else:
        req += recentActiveBills

    req = urllib2.urlopen(req).read()
    bill = json.loads(req)

    if bill_id:
        for i, cosponsor in enumerate(bill['cosponsors']):
            bill['cosponsors'][i] = specific_moc(cosponsor['id'])
    else:
        bill = bill['objects']
    # Each bill has these keys
    # ['last_action_at', 'introduced_on', 'committee_ids', 'congress', 
    # 'bill_type', 'related_bill_ids', 'last_vote_at', 'short_title', 'number', 
    # 'sponsor', 'chamber', 'official_title', 'popular_title', 'enacted_as', 'urls', 
    # 'withdrawn_cosponsors_count', 'sponsor_id', 'history', 'last_version_on', 'bill_id', 
    # 'cosponsors_count']
    return bill


### Routing ###
@app.route('/')
def home():
    if current_user.is_authenticated():
        if current_user.firstvisit:
            user = get_user({"email": current_user.email})
            id = user.id
            user = User.query.get(id)
            user.firstvisit = False
            try:
                db.session.commit()
            except:
                pass # TODO: Add logging
            return redirect('editprofile')
        else:
            return redirect('compatibility')
    return render_template('index.html')

@app.route('/compatibility', methods=['GET', 'POST'])
def compatibility():
    if current_user.is_authenticated():
        if request.method == 'POST':
            user = get_user({"email": current_user.email})
            id = user.id
            user = User.query.get(id)
            user.zipcode = request.form.get('zipcode')
            try:
                db.session.commit()
            except:
                return render_template('compatibility.html', alert_failure=True)
            #lat_long = get_lat_long(request.remote_addr)

        lmocs = local_mocs()
        votes = voting_history()
        mocs = all_mocs()
        return render_template('compatibility.html', mocs=mocs, lmocs=lmocs, timestamp_prettify=timestamp_prettify)
    return render_template('index.html')

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

@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if current_user.is_authenticated():
        firstvisit = current_user.firstvisit
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
                return render_template('editprofile.html', alert_failure=True, email=email, firstvisit=firstvisit)
            return render_template('editprofile.html', alert_success=True, email=email, firstvisit=firstvisit)
        return render_template('editprofile.html', email=email, firstvisit=firstvisit)
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/profile')
def profile():
    if current_user.is_authenticated():
        return render_template('profile.html', date_register = datetime.fromtimestamp(int(current_user.date_register)).strftime('%m/%d/%Y at %H:%M:%S'))
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/bill/<billID>')
def bill(billID):
    if current_user.is_authenticated():
        bill = congressional_legislation(billID)
        member = specific_moc(bill['sponsor']['id'])
        return render_template('bill.html', bill=bill, member=member, timestamp_prettify=timestamp_prettify)
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/votingrecord')
def votingrecord():
    if current_user.is_authenticated():
        votes = voting_history()
        return render_template('votingrecord.html', votes=votes)
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/vote')
def vote():
    if current_user.is_authenticated():
        legislation = congressional_legislation()
        return render_template('vote.html', legislation=legislation)
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

@app.route('/blog')
def blog():
    if current_user.is_authenticated():
        return render_template('blog.html')
    return render_template('index.html', error="Opps! You've gotta be logged in for that!")

### Admin Tools ###
@app.route('/show_db')
def show_db():
    users = []
    for user in db.session.query(User):
        users.append(dict(id=user.id, email=user.email, firstname=user.firstname, lastname=user.lastname, date_register=user.date_register))
    return render_template('show_db.html', users=users)

app.add_url_rule('/bills/<billID>', view_func=bill, methods=['GET'])


if __name__ == '__main__':
    app.run(host='0.0.0.0')
