import datetime
from functools import wraps

from views_base import ViewBase

from google.appengine.ext.webapp import template
from google.appengine.ext import ndb
from google.appengine.api import users

from models import (Show, Player, PlayerAction, ShowPlayer, ShowAction, Action,
					Theme, ActionVote, ThemeVote, Item, ItemVote,
					WildcardCharacter, WildcardCharacterVote,
					VOTE_AFTER_INTERVAL, ROLE_AFTER_INTERVAL, DISPLAY_VOTED)
from timezone import get_mountain_time, back_to_tz


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            redirect_uri = users.create_login_url(webapp2.get_request().uri)
            print redirect_uri
            return webapp2.redirect(redirect_uri, abort=True)
        return func(*args, **kwargs)
    return decorated_view


class CreateShow(ViewBase):
	@admin_required
	def get(self):
		context = {'players': Player.query().fetch(),
				   'themes': Theme.query(Theme.used == False).fetch()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		length = int(self.request.get('show_length'))
		scheduled_string = self.request.get('scheduled')
		theme_id = self.request.get('theme_id')
		player_list = self.request.get_all('player_list')
		action_intervals = self.request.get('action_intervals')
		context = {'players': Player.query().fetch(),
		           'themes': Theme.query(Theme.used == False).fetch()}
		if length and player_list and action_intervals:
			# Get the list of interval times
			try:
				interval_list = [int(x.strip()) for x in action_intervals.split(',')]
			except ValueError:
				raise ValueError("Invalid interval list '%s'. Must be comma separated.")
			if scheduled_string:
				scheduled = datetime.datetime.strptime(scheduled_string,
													   "%d.%m.%Y %H:%M")
			else:
				scheduled = get_mountain_time()
			theme = ndb.Key(Theme, int(theme_id))
			show = Show(length=length, scheduled=scheduled, theme=theme).put()
			# Add the action intervals to the show
			for interval in interval_list:
				player_action = PlayerAction(interval=interval).put()
				ShowAction(show=show, player_action=player_action).put()
			# Add the players to the show
			for player in player_list:
				player_key = ndb.Key(Player, int(player)).get().key
				ShowPlayer(show=show, player=player_key).put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))


class DeleteTools(ViewBase):
	@admin_required
	def get(self):
		context = {'shows': Show.query().fetch(),
				   'actions': Action.query(Action.used == False).fetch(),
				   'items': Item.query(Item.used == False).fetch(),
				   'characters': WildcardCharacter.query(
				   					WildcardCharacter.used == False).fetch(),
				   'themes': Theme.query(Theme.used == False).fetch()}
		self.response.out.write(template.render(self.path('delete_tools.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		deleted = None
		unused_deleted = False
		show_list = int(self.request.get('show_list'))
		action_list = self.request.get_all('action_list')
		item_list = self.request.get_all('item_list')
		theme_list = self.request.get_all('theme_list')
		delete_unused = self.request.get_all('delete_unused')
		# If action(s) were deleted
		if action_list:
			for action in action_list:
				action_entity = ndb.Key(Action, int(action)).get()
				# Get all the related action votes and delete them
				action_votes = ActionVote.query(ActionVote.action == action_entity.key).fetch()
				for av in action_votes:
					av.key.delete()
				action_entity.key.delete()
			deleted = 'Action(s)'
		# If item(s) were deleted
		if item_list:
			for item in item_list:
				item_entity = ndb.Key(Item, int(item)).get()
				# Get all the related item votes and delete them
				item_votes = ItemVote.query(ItemVote.item == item_entity.key).fetch()
				for av in item_votes:
					av.key.delete()
				item_entity.key.delete()
			deleted = 'Item(s)'
		# If character(s) were deleted
		if character_list:
			for character in character_list:
				character_entity = ndb.Key(WildcardCharacter, int(character)).get()
				# Get all the related character votes and delete them
				character_votes = WildcardCharacterVote.query(
								WildcardCharacterVote.character == character_entity.key).fetch()
				for av in character_votes:
					av.key.delete()
				character_entity.key.delete()
			deleted = 'Character(s)'
		# If theme(s) were deleted
		if theme_list:
			for theme in theme_list:
				theme_entity = ndb.Key(Theme, int(theme)).get()
				# Get all the related theme votes and delete them
				theme_votes = ThemeVote.query(ThemeVote.theme == theme_entity.key).fetch()
				for tv in theme_votes:
					tv.key.delete()
				theme_entity.key.delete()
			deleted = 'Theme(s)'
		# If show(s) were deleted
		if show_list:
			for show_id in show_list:
				show = ndb.Key(Show, int(show_id))
				show_actions = ShowAction.query(ShowAction.show == show).fetch()
				# Delete the actions that occurred within the show
				for show_action in show_actions:
					action = show_action.player_action.get().action
					if action:
						action.delete()
					show_action.player_action.delete()
					show_action.key.delete()
				# Delete player associations to the show
				show_players = ShowPlayer.query(ShowPlayer.show == show).fetch()
				for show_player in show_players:
					show_player.key.delete()
				# Delete the theme used in the show, if it existed
				if show.theme:
					show.theme.key.delete()
				# Delete the item used in the show, if it existed
				if show.item:
					show.item.key.delete()
				# Delete the character used in the show, if it existed
				if show.wildcard_character:
					show.wildcard_character.key.delete()
				show.delete()
				deleted = 'Show(s)'
		# Delete ALL un-used things
		if delete_unused:
			# Delete Un-used Actions
			unused_actions = Action.query(Action.used == False).fetch()
			for unused_action in unused_actions:
				# Get all the related action votes and delete them
				action_votes = ActionVote.query(ActionVote.action == unused_action.key).fetch()
				for av in action_votes:
					av.key.delete()
				# Delete the un-used actions
				unused_action.key.delete()
			# Delete Un-used Items
			unused_items = Item.query(Item.used == False).fetch()
			for unused_item in unused_items:
				# Get all the related item votes and delete them
				item_votes = ItemVote.query(ItemVote.item == unused_item.key).fetch()
				for iv in item_votes:
					iv.key.delete()
				# Delete the un-used items
				unused_items.key.delete()
			# Delete Un-used Characters
			unused_characters = WildcardCharacter.query(WildcardCharacter.used == False).fetch()
			for unused_character in unused_characters:
				# Get all the related character votes and delete them
				character_votes = WildcardCharacterVote.query(
									WildcardCharacterVote.wildcard_character == unused_character.key).fetch()
				for cv in character_votes:
					cv.key.delete()
				# Delete the un-used characters
				unused_character.key.delete()
			deleted = 'All Un-used Things'
		context = {'deleted': deleted,
				   'unused_deleted': unused_deleted,
				   'shows': Show.query().fetch(),
				   'actions': Action.query(Action.used == False).fetch(),
				   'items': Item.query(Item.used == False).fetch(),
				   'characters': WildcardCharacter.query(
				   					WildcardCharacter.used == False).fetch(),
				   'themes': Theme.query(Theme.used == False).fetch()}
		self.response.out.write(template.render(self.path('delete_tools.html'),
												self.add_context(context)))


class AddPlayers(ViewBase):
	@admin_required
	def get(self):
		self.response.out.write(template.render(self.path('add_players.html'),
												self.add_context()))

	@admin_required
	def post(self):
		created = False
		player_name = self.request.get('player_name')
		photo_filename = self.request.get('photo_filename')
		date_added = self.request.get('date_added')
		if player_name and photo_filename:
			if date_added:
				date_added = datetime.datetime.strptime(scheduled_string,
													   "%d.%m.%Y %H:%M")
			else:
				date_added = get_mountain_time()
			Player(name=player_name,
				   photo_filename=photo_filename,
				   date_added=date_added).put()
			created = True
		context = {'created': created}
		self.response.out.write(template.render(self.path('add_players.html'),
												self.add_context(context)))


class MockObject(object):
	def __init__(self, **kwargs):
		for key, value in kwargs.items():
			setattr(self, key, value)


class JSTestPage(ViewBase):
	@admin_required
	def get(self):
		
		player_freddy = MockObject(get = {'name':'Freddy',
						 			'photo_filename': 'freddy.jpg',
						 			'date_added': get_mountain_time().date()})
		player_dan = MockObject(get = {'name':'Dan',
						 			'photo_filename': 'dan.jpg',
						 			'date_added': get_mountain_time().date()})
		player_jeff = MockObject(get = {'name':'Jeff',
						 			'photo_filename': 'jeff.jpg',
						 			'date_added': get_mountain_time().date()})
		player_list = [player_freddy, player_dan, player_jeff]
		
		start_time = back_to_tz(get_mountain_time())
		end_time = start_time + datetime.timedelta(minutes=4)
		show_mock = type('Show',
						 (object,),
						 dict(scheduled = get_mountain_time(),
							  player_actions = [],
							  theme = 'Pirates',
							  length = 4,
							  start_time = start_time,
							  end_time = end_time,
							  start_time_tz = start_time,
							  end_time_tz = end_time,
							  running = True))
		available_actions = []
		for i in range(1, 4):
			
			player_action_mock = MockObject(interval = i,
							  player = player_list[i-1],
							  time_of_action = get_mountain_time(),
							  action = None)
			show_mock.player_actions.append(player_action_mock)
			action_mock = MockObject(description = 'Option %s' % i,
						 created_date = get_mountain_time().date(),
						 used = False,
						 vote_value = 0,
						 live_vote_value = 0)
			available_actions.append(action_mock)
		context	= {'show': show_mock,
				   'available_actions': available_actions,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL,
				   'ROLE_AFTER_INTERVAL': ROLE_AFTER_INTERVAL,
				   'DISPLAY_VOTED': DISPLAY_VOTED,
				   'mocked': self.request.GET.get('mock', 'full'),
				   'sample': self.request.GET.get('sample'),
				   'is_admin': self.request.GET.get('is_admin'),
				   'show_state': self.request.GET.get('show_state', 'interval')}
		self.response.out.write(template.render(self.path('js_test.html'),
												self.add_context(context)))
