import datetime
import random

from google.appengine.ext import ndb

from timezone import mountain_time, get_mountain_time, today


class Player(ndb.Model):
	name = ndb.StringProperty(required=True)
	photo_filename = ndb.StringProperty(required=True)
	date_added = ndb.DateTimeProperty()
	
	@property
	def img_path(self):
		return "/static/img/players/%s" % self.photo_filename


class Show(ndb.Model):
	scheduled = ndb.DateTimeProperty()
	theme = ndb.StringProperty()
	length = ndb.IntegerProperty(required=True)
	start_time = ndb.DateTimeProperty()
	end_time = ndb.DateTimeProperty()
	# Style in which to run the show
	show_style = ndb.StringProperty()
	
	@property
	def players(self):
		show_players = ShowPlayer.query(ShowPlayer.show == self.key).fetch()
		return [x.player.get() for x in show_players if getattr(x, 'player', None)]
	
	@property
	def deaths(self):
		death_intervals = ShowDeath.query(ShowDeath.show == self.key).fetch()
		return [x.death.get() for x in death_intervals if getattr(x, 'death', None) and x.death.get()]
	
	@property
	def running(self):
		if not self.start_time or not self.end_time:
			return False
		now = get_mountain_time()
		print "start time, ", self.start_time
		print "end time, ", self.end_time
		print "now, ", now
		if now >= self.start_time and now <= self.end_time:
			return True
		return False

	@property
	def is_today(self):
		return self.scheduled.date() == today
	
	@property
	def in_future(self):
		return self.scheduled.date() > today
	
	@property
	def in_past(self):
		return self.scheduled.date() < today
	
	def put(self, *args, **kwargs):
		# If start_time is specified, it must mean a show has started
		if self.start_time and self.length:
			# Set the end time of the show
			self.end_time = self.start_time + datetime.timedelta(minutes=self.length)
			# Make a copy of the list of players and randomize it
			rand_players = self.players
			random.shuffle(rand_players, random.random)
			# Get the potential death causes for the show
			today_causes = CauseOfDeath.query(
					CauseOfDeath.used != True,
					CauseOfDeath.created_date == today).fetch(keys_only=True)
			# If the number of causes is enough to fill all the deaths of the show
			if len(today_causes) >= len(self.deaths):
				rand_causes = today_causes
			# Otherwise, pull from the previous death pool
			else:
				rand_causes = CauseOfDeath.query(
								CauseOfDeath.used != True).fetch(keys_only=True)
			# Randomize the cause list
			random.shuffle(rand_causes, random.random)
			for death in self.deaths:
				# Pop a random player off the list
				death.player = rand_players.pop().key
				# Pop a random cause off the list
				death_cause = rand_causes.pop()
				# Set the cause to the death_cause key
				death.cause = death_cause
				# Get the cause entity
				cause_entity = death_cause.get()
				# Set the entity as used, and save it
				cause_entity.used = True
				cause_entity.put()
				death.time_of_death = self.start_time + \
									  datetime.timedelta(minutes=death.interval)
				death.put()
		return super(Show, self).put(*args, **kwargs)


class CauseOfDeath(ndb.Model):
	cause = ndb.StringProperty(required=True)
	created_date = ndb.DateProperty(required=True)
	used = ndb.BooleanProperty(default=False)

	def put(self, *args, **kwargs):
		self.created_date = mountain_time
		return super(CauseOfDeath, self).put(*args, **kwargs)	
	

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
	