import os
import urllib
from google.appengine.api import users
from google.appengine.ext import ndb
import jinja2
import webapp2
import datetime
import time
import uuid
from jinja2 import Environment

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_GUESTBOOK_NAME = 'default_guestbook'

SEPARATOR = '_'


def resource_key():
    day = datetime.datetime.now().day;
    month = datetime.datetime.now().month;
    year = datetime.datetime.now().year;
    return ndb.Key('Resource', str(day)+SEPARATOR+str(month)+SEPARATOR+str(year))

def reservation_key(user_id):
    currentTime = datetime.datetime.now()
        # To convert in EST/EDT
    delta = datetime.timedelta(hours = 5)
    currentTime = currentTime - delta
    day = str(currentTime.day)
    month = str(currentTime.month)
    year = str(currentTime.year)
    date = day+SEPARATOR+month+SEPARATOR+year
    return ndb.Key('Reservation', user_id+SEPARATOR+date)


class Reservations(ndb.Model):
    resourceName = ndb.StringProperty(indexed=False)
    resourceUid = ndb.StringProperty(indexed=False)
    reservedBy = ndb.StringProperty(indexed=True)
    startTime = ndb.DateTimeProperty(indexed=True)
    endTime = ndb.DateTimeProperty(indexed=False)
    uid = ndb.StringProperty(indexed=True)

## To remove
def enterOneReservation():
    reservation = Reservations(parent=reservation_key(users.get_current_user().user_id()))
    reservation.resourceName = 'Phone'
    reservation.reservedBy = users.get_current_user().email()
    reservation.startTime = datetime.datetime.strptime('1:00', "%H:%M")
    reservation.endTime = datetime.datetime.strptime('23:35', "%H:%M")
    reservation.uid = str(uuid.uuid4())
    reservation.put()

def getReservations(userId):
    currentTime = datetime.datetime.now()
    # To convert in EST/EDT
    delta = datetime.timedelta(hours = 5)
    currentTime = currentTime - delta
    hour = currentTime.hour
    minute = currentTime.minute
    currenTimeString = str(hour)+':'+str(minute)
    currentTimeObject = datetime.datetime.strptime(currenTimeString,'%H:%M')
    reservations_query = Reservations.query(ancestor=reservation_key(userId))
    reservations_query = reservations_query.order(Reservations.startTime)    
    reservations = reservations_query.fetch()
    reservations = [ r for r in reservations if r.endTime >= currentTimeObject ]   
    return reservations

class TimeSlot(ndb.Model):
    startTime = ndb.DateTimeProperty(indexed=False)
    endTime = ndb.DateTimeProperty(indexed=False)

class Resource(ndb.Model):
    name = ndb.StringProperty(indexed=False)
    availability = ndb.StructuredProperty(TimeSlot, repeated=True)
    tags = ndb.StringProperty(indexed=False, repeated = True)
    reservations = ndb.StructuredProperty(Reservations, repeated = True)
    owner = ndb.StringProperty(indexed=True)
    lastReservation = ndb.DateTimeProperty(indexed=True)
    uid = ndb.StringProperty(indexed=True)

def processAvailabilities(availabilities):
    result = ''
    for availability in availabilities:
        startTime = availability.startTime.strftime('%H:%M')
        endTime = availability.endTime.strftime('%H:%M')
        timeslot = startTime+"-" +endTime + " "
        result = result + timeslot
    return result

def processTags(tags):
    result = ''
    flag = 0
    for tag in tags:
        result = result + "/" + tag
    return result[1:]

def getResources():
    key = resource_key()
    resources_query = Resource.query(ancestor=key)
    resources = resources_query.order(-Resource.lastReservation).fetch()
    #processResources(resources)
    return resources    

def getMyResources(resources):
    myResources = [ r for r in resources if r.owner == users.get_current_user().email() ]
    return myResources

class MainPage(webapp2.RequestHandler):
    def get(self):
        #enterOneReservation()
        user = users.get_current_user()
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'

        if user is None:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            reservations = getReservations(user.user_id())
            resources = getResources()
            myResources = getMyResources(resources)

            template_values = {
                'user': user,
                'url': url,
                'url_linktext': url_linktext,
                'reservations': reservations,
                'resources': resources,
                'myResources': myResources,
            }

            JINJA_ENVIRONMENT.filters['processAvailabilities'] = processAvailabilities
            JINJA_ENVIRONMENT.filters['processTags'] = processTags
            template = JINJA_ENVIRONMENT.get_template('index.html')
            self.response.write(template.render(template_values))

class ResourceMain(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template = JINJA_ENVIRONMENT.get_template('resourceMain.html')
        self.response.write(template.render(template_values))
        

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
        resource.owner = str(users.get_current_user().email());
        resource.reservations = []
        resource.lastReservation = datetime.datetime.min
        resource.uid = str(uuid.uuid4())
        resource.put()

# Redirect to original landing page
        self.redirect('/')

JINJA_ENVIRONMENT.filters['processAvailabilities'] = processAvailabilities

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/addResource', AddResource),
    ('/resourceMain', ResourceMain)
], debug=True)