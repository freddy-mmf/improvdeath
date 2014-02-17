import datetime
import random

from google.appengine.ext import ndb


class Player(ndb.Model):
	name = ndb.StringProperty(required=True)
	photo_filename = ndb.StringProperty(required=True)
	date_added = ndb.DateTimeProperty(required=True,
									 auto_now_add=True)
	
	@property
	def img_path(self):
		return "/static/img/players/%s" % self.photo_filename


class Show(ndb.Model):
	scheduled = ndb.DateTimeProperty()
	length = ndb.IntegerProperty(required=True)
	start_time = ndb.DateTimeProperty()
	end_time = ndb.DateTimeProperty()
	
	@property
	def players(self):
		show_players = ShowPlayer.query(ShowPlayer.show == self.key).fetch()
		print "showplayers, ", show_players
		return [x.player for x in show_players if getattr(x, 'player', None)]
	
	@property
	def deaths(self):
		show_players = ShowDeath.query(ShowDeath.show == self.key).fetch()
		return [x.death for x in death_intervals if getattr(x, 'death', None)]
	
	@property
	def running(self):
		if not self.start_time or not ndbself.end_time:
			return False
		now = datetime.datetime.now()
		if now >= self.start_time and now <= self.end_time:
			return True
		return False

	@property
	def is_today(self):
		return self.scheduled.date() == datetime.date.today()
	
	@property
	def in_future(self):
		return self.scheduled.date() > datetime.date.today()
	
	@property
	def in_past(self):
		return self.scheduled.date() < datetime.date.today()
	
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
		return super(Show, self).put(*args, **kwargs)


class CauseOfDeath(ndb.Model):
	cause = ndb.StringProperty(required=True)
	created_date = ndb.DateProperty(required=True, auto_now_add=True)
	used = ndb.BooleanProperty(default=False)


class Death(ndb.Model):
	interval = ndb.IntegerProperty(required=True)
	player = ndb.KeyProperty(kind=Player)
	time_of_death = ndb.DateTimeProperty()
	cause = ndb.KeyProperty(kind=CauseOfDeath)


class ShowPlayer(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)


class ShowDeath(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	death = ndb.KeyProperty(kind=Death, required=True)

class Vote(ndb.Model):
	cause = ndb.KeyProperty(kind=CauseOfDeath, required=True)
	value = ndb.IntegerProperty(required=True, choices=[1, -1])
	ip = ndb.StringProperty(required=True)
	
	def put(self, *args, **kwargs):
		cause = kwargs.get('cause')
		ip = kwargs.get('ip')
		existing_vote = Vote.query(Vote.cause == cause,
								   Vote.ip == ip).get()
		if existing_vote:
			return self
		return super(Vote, self).put(*args, **kwargs)
	