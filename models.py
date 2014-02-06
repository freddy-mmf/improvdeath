from google.appengine.ext import db


class Player(db.Model):
    name = db.StringProperty(required=True)
    photo_key = db.blobstore.BlobReferenceProperty()
    date_added = db.DateTimeProperty(required=True,
                                     auto_now_add=True)


class Show(db.Model):
	scheduled = db.DateTimeProperty()
	length = db.IntegerProperty()
	time_started = db.DateTimeProperty()
	
	# Show affiliated players
    players = db.ListProperty(db.Key)
	# Show death intervals
    death_intervals = db.ListProperty(db.Key)


class Death(db.Model):
	show = db.ReferenceProperty(Show, required=True)
	player = db.ReferenceProperty(Player, required=True)
	time_of_death = db.DateTimeProperty(required=True,
                                     auto_now_add=True)
    method = db.StringProperty()


class DeathInterval(db.Model):
	minute = db.IntegerProperty()