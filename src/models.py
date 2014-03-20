import datetime
import random

from google.appengine.ext import ndb

from timezone import get_mountain_time, back_to_tz


def get_vote_percentage(subset_count, all_count):
	# If either of the two counts are zero, return zero percent
	if subset_count == 0 or all_count == 0:
		return 0
	return int(math.floor(100 * float(subset_count)/float(all_count)))


class Player(ndb.Model):
	name = ndb.StringProperty(required=True)
	photo_filename = ndb.StringProperty(required=True)
	date_added = ndb.DateTimeProperty()
	
	@property
	def img_path(self):
		return "/static/img/players/%s" % self.photo_filename
	
	@property
	def get_live_action_vote(self, interval, session_id):
		return LiveActionVote.query(
					LiveActionVote.player == self.key,
					LiveActionVote.interval == int(interval),
					LiveActionVote.created == get_mountain_time().date(),
					LiveActionVote.session_id == str(session_id)).get()

	@property
	def get_all_live_action_count(self, interval):
		return LiveActionVote.query(
						LiveActionVote.player == self.key,
						LiveActionVote.interval == int(interval),
						LiveActionVote.created == get_mountain_time().date()).count()

	@property
	def get_live_action_percentage(self, action, interval, all_votes):
		action_votes = LiveActionVote.query(
						LiveActionVote.action == action,
						LiveActionVote.player == self.key,
						LiveActionVote.interval == int(interval),
						LiveActionVote.created == get_mountain_time().date()).count()
		return get_vote_percentage(action_votes, all_votes)
	
	@property
	def get_role_vote(self, show, role):
		return RoleVote.query(
					RoleVote.player == self.key,
					RoleVote.show == show,
					RoleVote.role == role).get()


class Show(ndb.Model):
	scheduled = ndb.DateTimeProperty()
	theme = ndb.StringProperty()
	style = ndb.StringProperty(required=True, choices=['interval', 'hero'])
	act = ndb.StringProperty(required=True, choices=[1, 2])
	length = ndb.IntegerProperty(required=True)
	start_time = ndb.DateTimeProperty()
	end_time = ndb.DateTimeProperty()
	
	@property
	def start_time_tz(self):
		return back_to_tz(self.start_time)
	
	@property
	def end_time_tz(self):
		return back_to_tz(self.end_time)
	
	@property
	def scheduled_tz(self):
		return back_to_tz(self.scheduled)
	
	def get_player_action_by_interval(self, interval):
		for pa in self.player_actions:
			if pa.interval == int(interval):
				return pa
	
	def get_player_by_interval(self, interval):
		pa = self.get_player_action_by_interval(interval)
		return pa.player
		
	@property
	def players(self):
		show_players = ShowPlayer.query(ShowPlayer.show == self.key).fetch()
		return [x.player.get() for x in show_players if getattr(x, 'player', None)]
	
	@property
	def player_actions(self):
		action_intervals = ShowAction.query(ShowAction.show == self.key).fetch()
		return [x.player_action.get() for x in action_intervals if getattr(x, 'player_action', None) and x.player_action.get()]
	
	@property
	def running(self):
		#return True
		if not self.start_time or not self.end_time:
			return False
		now_tz = back_to_tz(get_mountain_time())
		if now_tz >= self.start_time_tz and now_tz <= self.end_time_tz:
			return True
		return False

	@property
	def is_today(self):
		return self.scheduled.date() == get_mountain_time().date()
	
	@property
	def in_future(self):
		return self.scheduled.date() > get_mountain_time().date()
	
	@property
	def in_past(self):
		return self.scheduled.date() < get_mountain_time().date()
	
	def put(self, *args, **kwargs):
		# If start_time is specified, it must mean a show has started
		if self.start_time and self.length:
			# Set the end time of the show
			self.end_time = self.start_time + datetime.timedelta(minutes=self.length)
			# Make a copy of the list of players and randomize it
			rand_players = self.players
			random.shuffle(rand_players, random.random)
			for player_action in self.player_actions:
				# If random players list gets empty, refill it with more players
				if len(rand_players) == 0:
					rand_players = self.players
					random.shuffle(rand_players, random.random)
				# Pop a random player off the list
				player_action.player = rand_players.pop().key
				player_action.time_of_action = self.start_time + \
									  datetime.timedelta(minutes=player_action.interval)
				player_action.put()
		return super(Show, self).put(*args, **kwargs)


class ShowPlayer(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)


class Action(ndb.Model):
	description = ndb.StringProperty(required=True)
	created_date = ndb.DateProperty(required=True)
	used = ndb.BooleanProperty(default=False)
	vote_value = ndb.IntegerProperty(default=0)
	live_vote_value = ndb.IntegerProperty(default=0)

	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(Action, self).put(*args, **kwargs)	


class ActionVote(ndb.Model):
	action = ndb.KeyProperty(kind=Action, required=True)
	session_id = ndb.StringProperty(required=True)
	
	def put(self, *args, **kwargs):
		action = Action.query(Action.key == self.action).get()
		action.vote_value += 1
		action.put()
		return super(ActionVote, self).put(*args, **kwargs)


class LiveActionVote(ndb.Model):
	action = ndb.KeyProperty(kind=Action, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)
	interval = ndb.IntegerProperty(required=True)
	session_id = ndb.StringProperty(required=True)
	created = ndb.DateProperty(required=True)

	def put(self, *args, **kwargs):
		action = Action.query(Action.key == self.action).get()
		action.live_vote_value += 1
		action.put()
		return super(LiveActionVote, self).put(*args, **kwargs)


class PlayerAction(ndb.Model):
	interval = ndb.IntegerProperty(required=True)
	player = ndb.KeyProperty(kind=Player)
	time_of_action = ndb.DateTimeProperty()
	action = ndb.KeyProperty(kind=Action)

	@property
	def time_of_action_tz(self):
		return back_to_tz(self.time_of_action)


class ShowAction(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player_action = ndb.KeyProperty(kind=PlayerAction, required=True)


class Theme(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	vote_value = ndb.IntegerProperty(default=0)
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(Theme, self).put(*args, **kwargs)


class ThemeVote(ndb.Model):
	theme = ndb.KeyProperty(kind=Theme, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		theme = Theme.query(Theme.key == self.theme).get()
		theme.vote_value += 1
		theme.put()
		return super(ThemeVote, self).put(*args, **kwargs)


class Item(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	vote_value = ndb.IntegerProperty(default=0)
	live_vote_value = ndb.IntegerProperty(default=0)
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(Item, self).put(*args, **kwargs)
	
	@property
	def get_live_item_vote(self, session_id):
		return LiveItemVote.query(
					LiveItemVote.item == self.key,
					LiveItemVote.session_id == str(session_id)).get()


class ItemVote(ndb.Model):
	item = ndb.KeyProperty(kind=Item, required=True)
	session_id = ndb.StringProperty(required=True)
	
	def put(self, *args, **kwargs):
		item = Item.query(Item.key == self.item).get()
		item.vote_value += 1
		item.put()
		return super(ItemVote, self).put(*args, **kwargs)


class LiveItemVote(ndb.Model):
	item = ndb.KeyProperty(kind=Item, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		item = Item.query(Item.key == self.item).get()
		item.live_vote_value += 1
		item.put()
		return super(LiveItemVote, self).put(*args, **kwargs)


class WildcardCharacter(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	vote_value = ndb.IntegerProperty(default=0)
	live_vote_value = ndb.IntegerProperty(default=0)
	
	@property
	def get_live_wc_vote(self, session_id):
		return LiveWildcardCharacterVote.query(
					LiveWildcardCharacterVote.wildcard_character == self.key,
					LiveWildcardCharacterVote.session_id == str(session_id)).get()
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(WildcardCharacter, self).put(*args, **kwargs)


class WildcardCharacterVote(ndb.Model):
	wildcard_character = ndb.KeyProperty(kind=WildcardCharacter, required=True)
	session_id = ndb.StringProperty(required=True)
	
	def put(self, *args, **kwargs):
		wildcard_character = WildcardCharacter.query(
			WildcardCharacter.key == self.wildcard_character).get()
		wildcard_character.vote_value += 1
		wildcard_character.put()
		return super(WildcardCharacterVote, self).put(*args, **kwargs)


class LiveWildcardCharacterVote(ndb.Model):
	wildcard_character = ndb.KeyProperty(kind=WildcardCharacter, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		wildcard_character = WildcardCharacter.query(
			WildcardCharacter.key == self.wildcard_character).get()
		wildcard_character.live_vote_value += 1
		wildcard_character.put()
		return super(LiveWildcardCharacterVote, self).put(*args, **kwargs)


class RoleVote(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)
	role = ndb.StringProperty(required=True, choices=['hero',
													   'villain',
													   'shapeshifter'])
	live_vote_value = ndb.IntegerProperty(default=0)

	@property
	def get_live_role_vote(self, session_id):
		return LiveRoleVote.query(
					LiveRoleVote.role_vote == self.key,
					LiveRoleVote.session_id == str(session_id)).get()


class LiveRoleVote(ndb.Model):
	role_vote = ndb.KeyProperty(kind=RoleVote, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		self.role_vote.live_vote_value += 1
		self.role_vote.save()
		return super(LiveRoleVote, self).put(*args, **kwargs)