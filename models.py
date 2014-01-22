from google.appengine.ext import db


class Player(db.Model):
    name = db.StringProperty(required=True)
    photo_key = db.blobstore.BlobReferenceProperty()
    date_added = db.DateTimeProperty(required=True,
                                     auto_now_add=True)


class Show(db.Model):
	date_run = db.DateTimeProperty()
	length = db.IntegerProperty()
	
	# Show affiliated players
    players = db.ListProperty(db.Key)
	# Show death intervals
    intervals = db.ListProperty(db.Key)

class Death(db.Model):
	show = db.ReferenceProperty(Show)
	player = db.ReferenceProperty(Player)
	created_date = db.DateTimeProperty(required=True,
                                     auto_now_add=True)
	
	@property
    def used(self):
        if show and player:
        	return True
        return False

class Interval(db.Model):
	minute = db.IntegerProperty()