import datetime
import random

from google.appengine.ext import db


class Player(db.Model):
	name = db.StringProperty(required=True)
	photo_filename = db.StringProperty(required=True)
	date_added = db.DateTimeProperty(required=True,
									 auto_now_add=True)
	
	@property
	def img_path(self):
		return "/static/img/players/%s" % self.photo_filename


class Show(db.Model):
	scheduled = db.DateTimeProperty()
	length = db.IntegerProperty(required=True)
	start_time = db.DateTimeProperty()
	end_time = db.DateTimeProperty()
	
	# Show affiliated players
	players = db.ListProperty(db.Key)
	
	@property
	def deaths(self):
		q = Death.all()
		q.filter("show =", self)
		return q.run()
	
	@property
	def running(self):
		if not self.start_time or not self.end_time:
			return False
		now = datetime.datetime.now()
		if now >= self.start_time and now <= self.end_time:
			return True
		return False
	
	def put(self, *args, **kwargs):
		start_time = kwargs.get('start_time')
		# If start_time is specified, it must mean a show has started
		if start_time and self.length:
			# Set the end time of the show
			self.end_time = start_time + datetime.timedelta(minutes=self.length)
			# Make a copy of the list of players and randomize it
			rand_players = self.players
			random.shuffle(rand_players)
			for death in self.deaths:
				death.player = rand_players.pop()
				death.time_of_death = self.start_time + \
									  datetime.timedelta(minutes=death.interval)
				death.put()
		super(Show, self).put(*args, **kwargs)


class Death(db.Model):
	show = db.ReferenceProperty(Show, required=True)
	interval = db.IntegerProperty(required=True)
	player = db.ReferenceProperty(Player)
	time_of_death = db.DateTimeProperty()
	method = db.StringProperty()
