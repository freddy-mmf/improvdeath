import datetime
import random

from google.appengine.ext import ndb

from timezone import get_mountain_time, back_to_tz

VOTE_AFTER_INTERVAL = 10
ROLE_AFTER_INTERVAL = 15
DISPLAY_VOTED = 5


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


class Theme(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	used = ndb.BooleanProperty(default=False)
	vote_value = ndb.IntegerProperty(default=0)
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(Theme, self).put(*args, **kwargs)


class Item(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	used = ndb.BooleanProperty(default=False)
	vote_value = ndb.IntegerProperty(default=0)
	live_vote_value = ndb.IntegerProperty(default=0)
	
	@property
	def get_live_item_vote(self, session_id):
		return LiveItemVote.query(
					LiveItemVote.item == self.key,
					LiveItemVote.session_id == str(session_id)).get()
	
	def live_vote_percent(self, show):
		all_count = LiveItemVote.query(LiveItemVote.show == show).count()
		return get_vote_percentage(self.live_vote_value, all_count)
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(Item, self).put(*args, **kwargs)


class WildcardCharacter(ndb.Model):
	created_date = ndb.DateTimeProperty(required=True)
	name = ndb.StringProperty(required=True)
	used = ndb.BooleanProperty(default=False)
	vote_value = ndb.IntegerProperty(default=0)
	live_vote_value = ndb.IntegerProperty(default=0)
	
	@property
	def get_live_wc_vote(self, session_id):
		return LiveWildcardCharacterVote.query(
					LiveWildcardCharacterVote.wildcard_character == self.key,
					LiveWildcardCharacterVote.session_id == str(session_id)).get()
	
	def live_vote_percent(self, show):
		all_count = LiveWildcardCharacterVote.query(
			LiveWildcardCharacterVote.show == show).count()
		return get_vote_percentage(self.live_vote_value, all_count)
	
	def put(self, *args, **kwargs):
		self.created_date = get_mountain_time()
		return super(WildcardCharacter, self).put(*args, **kwargs)


class Show(ndb.Model):
	scheduled = ndb.DateTimeProperty()
	theme = ndb.KeyProperty(kind=Theme)
	length = ndb.IntegerProperty(required=True)
	start_time = ndb.DateTimeProperty()
	end_time = ndb.DateTimeProperty()
	item_vote_end = ndb.DateTimeProperty()
	role_vote_end = ndb.DateTimeProperty()
	wildcard_vote_end = ndb.DateTimeProperty()
	shapeshifter_vote_end = ndb.DateTimeProperty()
	item = ndb.KeyProperty(kind=Item)
	hero = ndb.KeyProperty(kind=Player)
	villain = ndb.KeyProperty(kind=Player)
	wildcard_character = ndb.KeyProperty(kind=WildcardCharacter)
	shapeshifter = ndb.KeyProperty(kind=Player)
	
	
	
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
	
	@property
	def current_vote_state(self):
		now = get_mountain_time()
		# Get timezone for comparisons
		now_tz = back_to_tz(now)
		vote_type_list = ['item', 'role', 'wildcard', 'shapeshifter']
		# Go through all the vote times to see if they've started
		for vote_type in vote_type_list:
			if vote_type == 'role':
				vote_length = ROLE_AFTER_INTERVAL
			else:
				vote_length = VOTE_AFTER_INTERVAL
			time_property = "%s_vote_init" % vote_type
			init_time = getattr(self, time_property, None)
			# If the vote has started
			if init_time:
				# Get the timezone datetime of the start of the vote type
				init_time_tz = back_to_tz(init_time)
				# Get the end of the voting period for the type
				vote_end = init_time_tz + datetime.timedelta(seconds=vote_length)
				# Get the end of the overall display of the type
				display_end = vote_end + datetime.timedelta(seconds=DISPLAY_VOTED)
				# If we're in the voting period of this type
				if now_tz >= init_time_tz and now_tz <= vote_end:
					return {'state': vote_type, 'display': 'voting'}
				elif now_tz >= vote_end and now_tz <= display_end:
					return {'state': vote_type, 'display': 'result'}
					
		return {'state': 'default'}
	
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
		# If a theme was specified, set the theme as used
		if self.theme:
			theme_entity = self.theme.get()
			theme_entity.used = True
			theme_entity.put()
		# If an item was specified, set the item as used
		if self.item:
			item_entity = self.item.get()
			item_entity.used = True
			item_entity.put()
		# If a character was specified, set the item as used
		if self.wildcard_character:
			wildcard_character_entity = self.wildcard_character.get()
			wildcard_character_entity.used = True
			wildcard_character_entity.put()
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


class ThemeVote(ndb.Model):
	theme = ndb.KeyProperty(kind=Theme, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		theme = Theme.query(Theme.key == self.theme).get()
		theme.vote_value += 1
		theme.put()
		return super(ThemeVote, self).put(*args, **kwargs)


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
	show = ndb.KeyProperty(kind=Show, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		item = Item.query(Item.key == self.item).get()
		item.live_vote_value += 1
		item.put()
		return super(LiveItemVote, self).put(*args, **kwargs)


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
	show = ndb.KeyProperty(kind=Show, required=True)
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		wildcard_character = WildcardCharacter.query(
			WildcardCharacter.key == self.wildcard_character).get()
		wildcard_character.live_vote_value += 1
		wildcard_character.put()
		return super(LiveWildcardCharacterVote, self).put(*args, **kwargs)


def get_or_create_role_vote(show, player, role):
	role_vote = RoleVote.query(RoleVote.show == show.key,
							   RoleVote.player == player.key,
							   RoleVote.role == role).get()
	if not role_vote:
		role_vote = RoleVote(show=show,
				 player=player,
				 role=role).put().get()
	return role_vote


class RoleVote(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)
	role = ndb.StringProperty(required=True, choices=['hero',
													  'villain',
													  'shapeshifter'])
	live_vote_value = ndb.IntegerProperty(default=0)

	@property
	def live_role_vote_percent(self):
		all_count = LiveRoleVote.query(
			LiveRoleVote.show == self.show,
			LiveRoleVote.role == self.role).count()
		return get_vote_percentage(self.live_vote_value, all_count)

	@property
	def get_live_role_vote(self, session_id):
		return LiveRoleVote.query(
					LiveRoleVote.show == self.show,
					LiveRoleVote.player == self.player,
					LiveRoleVote.role == self.role,
					LiveRoleVote.session_id == str(session_id)).get()


class LiveRoleVote(ndb.Model):
	show = ndb.KeyProperty(kind=Show, required=True)
	player = ndb.KeyProperty(kind=Player, required=True)
	role = ndb.StringProperty(required=True, choices=['hero',
													   'villain',
													   'shapeshifter'])
	session_id = ndb.StringProperty(required=True)

	def put(self, *args, **kwargs):
		role_vote = RoleVote.query(RoleVote.show == self.show,
								   RoleVote.player == self.player,
								   RoleVote.role == self.role).get()
		role_vote.live_vote_value += 1
		role_vote.save()
		return super(LiveRoleVote, self).put(*args, **kwargs)