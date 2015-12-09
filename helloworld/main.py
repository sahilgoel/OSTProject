import os
import urllib
from google.appengine.api import users
from google.appengine.ext import ndb
import jinja2
import webapp2
import datetime
import time

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_GUESTBOOK_NAME = 'default_guestbook'

SEPARATOR = '_'

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.

def guestbook_key(guestbook_name=DEFAULT_GUESTBOOK_NAME):
    """Constructs a Datastore key for a Guestbook entity.
    We use guestbook_name as the key.
    """
    return ndb.Key('Guestbook', guestbook_name)

def resource_key():
    day = datetime.datetime.now().day;
    month = datetime.datetime.now().month;
    year = datetime.datetime.now().year;
    return ndb.Key('Resource', str(day)+SEPARATOR+str(month)+SEPARATOR+str(year))

def reservation_key(user_id):
    return ndb.Key('Reservation', user_id)

class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)

class Greeting(ndb.Model):
    """A main model for representing an individual Guestbook entry."""
    author = ndb.StructuredProperty(Author)
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)

class Reservations(ndb.Model):
    resourceName = ndb.StringProperty(indexed=False)
    reservedBy = ndb.StringProperty(indexed=False)
    startTime = ndb.DateTimeProperty(indexed=True)
    endTime = ndb.DateTimeProperty(indexed=True)

class TimeSlot(ndb.Model):
    startTime = ndb.DateTimeProperty(indexed=False)
    endTime = ndb.DateTimeProperty(indexed=False)

class Resource(ndb.Model):
    name = ndb.StringProperty(indexed=False)
    availability = ndb.StructuredProperty(TimeSlot, repeated=True)
    tags = ndb.StringProperty(indexed=False, repeated = True)
    reservations = ndb.StructuredProperty(Reservations, repeated = True)

class MainPage(webapp2.RequestHandler):
    def get(self):
        #key = resource_key()
        #resources_query = Resources.query(ancestor=key)
        #resources = resources_query.fetch(10)
        user = users.get_current_user()
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'
        if user is None:
            self.redirect(users.create_login_url(self.request.uri))

        currentTime = datetime.datetime.now()
        hour = currentTime.hour
        minute = currentTime.minute
        currenTimeString = str(hour)+':'+str(minute)
        currentTimeObject = datetime.datetime.strptime(currenTimeString,'%H:%M')
        reservations_query = Reservations.query(ancestor=reservation_key(str(user.user_id)))
        reservations_query = reservations_query.order(Reservations.startTime)    
        reservations = reservations_query.fetch()

        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_GUESTBOOK_NAME)
        greetings_query = Greeting.query(
            ancestor=guestbook_key(guestbook_name)).order(-Greeting.date)
        greetings = greetings_query.fetch(10)

        template_values = {
            'user': user,
            'greetings': greetings,
            'guestbook_name': urllib.quote_plus(guestbook_name),
            'url': url,
            'url_linktext': url_linktext,
            'reservations': reservations,
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

class Guestbook(webapp2.RequestHandler):
    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each
        # Greeting is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        guestbook_name = self.request.get('guestbook_name',
                                          DEFAULT_GUESTBOOK_NAME)
        greeting = Greeting(parent=guestbook_key(guestbook_name))

        if users.get_current_user():
            greeting.author = Author(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        greeting.content = self.request.get('content')
        greeting.put()

        query_params = {'guestbook_name': guestbook_name}
        self.redirect('/?' + urllib.urlencode(query_params))


class AddResource(webapp2.RequestHandler):
    def get(self):
        #user_name = users.get_current_user()
        template = JINJA_ENVIRONMENT.get_template('addResource.html')
        template_values = {}
        self.response.write(template.render(template_values))
    def post(self):
        template = JINJA_ENVIRONMENT.get_template('addResource.html')
        resourceName = self.request.get('resourceName')
        startTime = self.request.get('startTime')
        endTime = self.request.get('endTime')
        tags = self.request.get('tags')
        error = None
        if resourceName is None or len(resourceName) == 0:
            error = 'Resource Name cannot be empty'
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': startTime,
              'endTime': endTime,
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return

##      Start Time Processing
        startTime = self.request.get('startTime')
        if startTime is None or len(startTime) == 0:
            error = 'Start time cannot be empty'
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'endTime': endTime,
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return

        tokens = startTime.split(":")
        if len(tokens) != 2:
            error = "Start time should be entered in format HH:MM"
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': '',
              'endTime': endTime,
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return
        hours = tokens[0]
        minutes = tokens[1]
        if not(hours.isdigit()) or not(hours.isdigit()):
            error = "HH and MM should be numbers only"
        elif int(hours) < 0 or int(hours) >= 24:
            error = "HH should be between 00 and 23"
        elif int(minutes) < 0 or int(minutes) >= 60:
            error = "MM should be between 00 and 60"
        if not(error is None):
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': '',
              'endTime': endTime,
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return


## End Time Processing
        if endTime is None or len(endTime) == 0:
            error = 'Start time cannot be empty'
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': startTime,
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return

        tokens = endTime.split(":")
        if len(tokens) != 2:
            error = "End time should be entered in format HH:MM"
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': startTime,
              'endTime': '',
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return
        hours = tokens[0]
        minutes = tokens[1]
        if not(hours.isdigit()) or not(hours.isdigit()):
            error = "HH and MM should be numbers only"
        elif int(hours) < 0 or int(hours) >= 24:
            error = "HH should be between 00 and 23"
        elif int(minutes) < 0 or int(minutes) >= 60:
            error = "MM should be between 00 and 60"

        
        if error is None:
            time1 = datetime.datetime.strptime(startTime,'%H:%M')
            time2 = datetime.datetime.strptime(endTime, '%H:%M')
            if time2 <= time1:
                error = "End time should be after Start time"

        if not(error is None):
            template_values = {
              'error': error,
              'resourceName': resourceName,
              'startTime': startTime,
              'endTime': '',
              'tags': tags,
            }
            self.response.write(template.render(template_values))
            return

## Tags Processing
        tokens = tags.split(",")
        tokens = [ s.strip() for s in tokens ]

# Get Key and add to Datastore
        resource = Resource(parent=resource_key())
        resource.name = resourceName;
        t_startTime = datetime.datetime.strptime(startTime, '%H:%M')
        t_endTime = datetime.datetime.strptime(endTime, '%H:%M')
        resource.availability = [TimeSlot(startTime = t_startTime, endTime = t_endTime)]
        resource.tags = tokens
        resource.reservations = []
        resource.put()

# Redirect to original landing page
        self.redirect('/')

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/sign', Guestbook),
    ('/addResource', AddResource)
], debug=True)