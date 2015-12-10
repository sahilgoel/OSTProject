import os
import urllib
from google.appengine.api import users
from google.appengine.ext import ndb
#from google.appengine.api import datastore
import jinja2
import webapp2
import datetime
import time
import uuid
import copy
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
    duration = ndb.StringProperty(indexed=False)
    uid = ndb.StringProperty(indexed=True)


def getCurrentTimeObject():
    currentTime = datetime.datetime.now()
    # To convert in EST/EDT
    delta = datetime.timedelta(hours = 5)
    currentTime = currentTime - delta
    hour = currentTime.hour
    minute = currentTime.minute
    currenTimeString = str(hour)+':'+str(minute)
    currentTimeObject = datetime.datetime.strptime(currenTimeString,'%H:%M')
    return currentTimeObject

def getReservations(userId):
    currentTimeObject = getCurrentTimeObject()
    reservations_query = Reservations.query(ancestor=reservation_key(userId))
    reservations_query = reservations_query.order(Reservations.startTime)    
    reservations = reservations_query.fetch()
    print reservations
    print currentTimeObject
    reservations = [ r for r in reservations if r.startTime + datetime.timedelta(minutes = int(r.duration)) >= currentTimeObject ] 
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

def timeCompare(t1, t2):
    if t1.startTime > t2.startTime:
        return 1
    if t1.startTime == t2.startTime:
        return 0
    if t1.startTime < t2.startTime:
        return -1

def processAvailabilities(availabilities):
    result = ''
    if availabilities is None:
        return result
    availabilities.sort(timeCompare)
    for availability in availabilities:
        startTime = availability.startTime.strftime('%H:%M')
        endTime = availability.endTime.strftime('%H:%M')
        timeslot = startTime+"-" +endTime + "     "
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

def getResourceFromUid(resourceUid):
    key = resource_key()
    resources_query = Resource.query(Resource.uid == resourceUid)
    resource = resources_query.fetch()
    resource = resource[0]
    return resource

def getMyResources(resources):
    myResources = [ r for r in resources if r.owner == users.get_current_user().email() ]
    return myResources

def checkTimeFormat(time):
    if(len(time.split(":")) != 2):
        return True
    return False

def checkLimits(time):
    tokens = time.split(":")
    hours = int(tokens[0])
    minutes = int(tokens[1])
    if hours<0 or hours>=24 or minutes<0 or minutes>=60:
        return True
    return False

def checkDuration(duration):
    if not(duration.isdigit()):
        return True
    duration = int(duration)
    if duration <= 0:
        return True

def checkAndModifyAvailability(resource, startTime, duration):
    startTime = datetime.datetime.strptime(startTime,'%H:%M')
    delta = datetime.timedelta(minutes = int(duration))
    endTime = startTime + delta
    result = None
    for availability in resource.availability:
        if availability.startTime <= startTime and availability.endTime >= endTime:
            result = availability
            break
    # Resource is not available
    if result is None:
        return True
    resource.availability.remove(result)
    resultFirst = result
    resultSecond = copy.deepcopy(resultFirst)
    resultFirst.endTime = startTime - datetime.timedelta(minutes = 1)
    resultSecond.startTime = endTime
    resource.availability.append(resultFirst)
    resource.availability.append(resultSecond)
    resource.put()

def addReservation(uid, startTime, duration, resource):
    reservation = Reservations(parent=reservation_key(users.get_current_user().user_id()))
    reservation.reservedBy = str(users.get_current_user().email())
    reservation.startTime = datetime.datetime.strptime(startTime,'%H:%M')
    reservation.duration = duration
    reservation.resourceName = resource.name
    reservation.resourceUid = uid
    reservation.uid = str(uuid.uuid4())
    reservation.put()
    resource.reservations.append(reservation)
    resource.lastReservation = datetime.datetime.now()
    resource.put()


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

class AddReservation(webapp2.RequestHandler):
    def get(self):
        resourceUid = self.request.GET['uid']
        resource = Resource.query(Resource.uid == resourceUid).get()
        template_values = {
            'uid': resourceUid,
        }
        template = JINJA_ENVIRONMENT.get_template('addReservation.html')
        self.response.write(template.render(template_values))
    def post(self):
        uid = self.request.get('uid')
        startTime = self.request.get('startTime')
        duration = self.request.get('duration')
        error = checkTimeFormat(startTime)
        errorMsg = None
        if error:
            errorMsg = 'Please enter time in HH:MM format'
        if errorMsg is None:
            error = checkLimits(startTime)
            if error:
                errorMsg = 'Time should be between 00:00 and 23:59'
        if errorMsg is None:
            error = checkDuration(duration)
            if error:
                errorMsg = 'Duration should be a positive number'
        if errorMsg is None:
            resource = Resource.query(Resource.uid == uid).get()
            error = checkAndModifyAvailability(resource, startTime, duration)
            if error:
                errorMsg = 'Resource is not available during that time'
        if error:
            template_values = {
                'uid' : uid,
                'startTime': startTime,
                'duration': duration,
                'error' : errorMsg,
            }
            template = JINJA_ENVIRONMENT.get_template('addReservation.html')
            self.response.write(template.render(template_values))
            return

        # If everything fine, then add reservation in datastore
        resource = Resource.query(Resource.uid == uid).get()
        addReservation(uid, startTime, duration, resource)
        self.redirect('/')



class ResourceMain(webapp2.RequestHandler):
    def get(self):
        resourceUid = self.request.GET['uid']
        resource = getResourceFromUid(resourceUid)
        currentTimeObject = getCurrentTimeObject()
        resource.reservations = [ r for r in resource.reservations if 
            r.startTime + datetime.timedelta(minutes = int(r.duration)) >= currentTimeObject ]
        currentUser = str(users.get_current_user().email())
        template_values = {
            'resource':resource,
            'currentUser':currentUser,
        }
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
    ('/resourceMain', ResourceMain),
    ('/addReservation', AddReservation)
], debug=True)