import datetime
import json
from functools import wraps
import random

import webapp2
from google.appengine.ext.webapp import template
from google.appengine.ext import ndb
from google.appengine.api import users

from views_base import ViewBase

from models import (Show, Player, PlayerAction, ShowPlayer, ShowAction, Action,
					Theme, ActionVote, ThemeVote,
					VotingTest, LiveVotingTest, RoleVote,
					VOTE_AFTER_INTERVAL, ROLE_TYPES, VOTE_TYPES,
					get_current_show)
from timezone import get_mountain_time, back_to_tz


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            redirect_uri = users.create_login_url(webapp2.get_request().uri)
            return webapp2.redirect(redirect_uri, abort=True)
        return func(*args, **kwargs)
    return decorated_view


#### RESETS LIVE ACTION VOTES ####
def reset_action_live_votes():
	reset_actions = Action.query(Action.used == False,
				 				 Action.live_vote_value > 0).fetch()
	# Reset all actions that haven't been used, but have a live_vote_value, to zero
	for ra in reset_actions:
		# Set the actions live_vote_value to zero
		ra.live_vote_value = 0
		ra.put()


class ShowPage(ViewBase):
	@admin_required
	def get(self, show_id):
		show = ndb.Key(Show, int(show_id)).get()
		available_actions = len(Action.query(
							   Action.used == False).fetch())
		context	= {'show': show,
				   'now_tz': back_to_tz(get_mountain_time()),
				   'available_actions': available_actions,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))
	
	@admin_required
	def post(self, show_id):
		show = ndb.Key(Show, int(show_id)).get()
		# Admin is starting the show
		if self.request.get('interval_vote') and self.context.get('is_admin', False):
			# Get the next interval
			next_interval = show.get_next_interval(show.current_interval)
			# If there is a next interval
			if next_interval != None:
				# Set the current interval to the next interval
				show.current_interval = next_interval
				# Set the start time of this interval vote
				show.interval_vote_init = get_mountain_time()
				show.put()
			# Reset all actions that haven't been used, but have a live_vote_value, to zero
			reset_action_live_votes()
		# Admin is starting item vote
		elif self.request.get('test_vote') and self.context.get('is_admin', False):
			show.test = None
			# Delete all live voting test votes
			for lvt in LiveVotingTest.query().fetch():
				lvt.key.delete()
			# Delete all voting test objects
			for vt in VotingTest.query().fetch():
				vt.key.delete()
			# Create a set of five test votes
			VotingTest(name="I'M JAZZED! START THE SHOW ALREADY!").put()
			VotingTest(name="I'm VERY interested in... whatever this is...").put()
			VotingTest(name="Present").put()
			VotingTest(name="Meh").put()
			VotingTest(name="If you notice me sleeping in the audience, try and keep it down. Thanks.").put()

			show.test_vote_init = get_mountain_time()
			show.put()
		# Admin is starting hero vote
		elif self.request.get('hero_vote') and self.context.get('is_admin', False):
			show.hero_vote_init = get_mountain_time()
			show.put()
		# Admin is starting villain vote
		elif self.request.get('villain_vote') and self.context.get('is_admin', False):
			show.villain_vote_init = get_mountain_time()
			show.put()
		# Admin is starting incident vote
		elif self.request.get('incident_vote') and self.context.get('is_admin', False):
			# Set all actions that haven't been used, but have a live_vote_value, to zero
			reset_action_live_votes()
			show.incident_vote_init = get_mountain_time()
			show.put()
		# Admin is starting the shapeshifter vote
		elif self.request.get('shapeshifter_vote') and self.context.get('is_admin', False):
			show.shapeshifter_vote_init = get_mountain_time()
			show.put()
		# Admin is starting the lover vote
		elif self.request.get('lover_vote') and self.context.get('is_admin', False):
			show.lover_vote_init = get_mountain_time()
			show.put()
		# Admin is starting a recap
		elif self.request.get('recap') and self.context.get('is_admin', False):
			show.recap_init = get_mountain_time()
			show.recap_type = self.request.get('recap')
			show.put()
		# Admin is locking/unlocking the voting
		elif self.request.get('lock_vote') and self.context.get('is_admin', False):
			# Toggle the lock/unlock
			show.locked = not show.locked
			show.put()
		available_actions = len(Action.query(
							   Action.used == False).fetch())
		context	= {'show': show,
				   'now_tz': back_to_tz(get_mountain_time()),
				   'available_actions': available_actions,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))		


class CreateShow(ViewBase):
	@admin_required
	def get(self):
		context = {'players': Player.query().fetch(),
				   'themes': Theme.query(Theme.used == False,
				   				).order(-Theme.vote_value).fetch()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		scheduled_string = self.request.get('scheduled')
		theme_id = self.request.get('theme_id')
		player_list = self.request.get_all('player_list')
		action_intervals = self.request.get('action_intervals')
		context = {'players': Player.query().fetch(),
		           'themes': Theme.query(Theme.used == False).fetch()}
		if player_list and action_intervals:
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
			show = Show(scheduled=scheduled, theme=theme).put()
			players = []
			# Add the players to the show
			for player in player_list:
				player_key = ndb.Key(Player, int(player)).get().key
				players.append(player_key)
				ShowPlayer(show=show, player=player_key).put()
			# Make a copy of the list of players and randomize it
			rand_players = list(players)
			random.shuffle(rand_players, random.random)
			# Add the action intervals to the show
			for interval in interval_list:
				# If random players list gets empty, refill it with more players
				if len(rand_players) == 0:
					rand_players = list(players)
					random.shuffle(rand_players, random.random)
				# Pop a random player off the list and create a PlayerAction
				player_action = PlayerAction(interval=interval,
											 player=rand_players.pop()).put()
				ShowAction(show=show, player_action=player_action).put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))


class DeleteTools(ViewBase):
	@admin_required
	def get(self):
		context = {'shows': Show.query().fetch(),
				   'actions': Action.query(Action.used == False).fetch(),
				   'themes': Theme.query(Theme.used == False).fetch()}
		self.response.out.write(template.render(self.path('delete_tools.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		deleted = None
		unused_deleted = False
		show_list = self.request.get_all('show_list')
		action_list = self.request.get_all('action_list')
		item_list = self.request.get_all('item_list')
		character_list = self.request.get_all('character_list')
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
			for show in show_list:
				show_entity = ndb.Key(Show, int(show)).get()
				show_actions = ShowAction.query(ShowAction.show == show_entity.key).fetch()
				# Delete the actions that occurred within the show
				for show_action in show_actions:
					action = show_action.player_action.get().action
					if action:
						action.delete()
					show_action.player_action.delete()
					show_action.key.delete()
				# Delete player associations to the show
				show_players = ShowPlayer.query(ShowPlayer.show == show_entity.key).fetch()
				for show_player in show_players:
					show_player.key.delete()
				# Delete all Role votes
				role_votes = RoleVote.query(RoleVote.show == show_entity.key).fetch()
				for role_vote in role_votes:
					role_vote.key.delete()
				# Delete the theme used in the show, if it existed
				if show_entity.theme:
					show_entity.theme.delete()
				show_entity.key.delete()
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
			deleted = 'All Un-used Actions'
		context = {'deleted': deleted,
				   'unused_deleted': unused_deleted,
				   'shows': Show.query().fetch(),
				   'actions': Action.query(Action.used == False).fetch(),
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
				date_added = datetime.datetime.strptime(date_added,
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


class IntervalTimer(ViewBase):
	@admin_required
	def get(self):
		context = {'show': get_current_show(),
				  'now_tz': back_to_tz(get_mountain_time())}
		self.response.out.write(template.render(self.path('interval_timer.html'),
												self.add_context(context)))


class MockObject(object):
	def __init__(self, **kwargs):
		for key, value in kwargs.items():
			setattr(self, key, value)


class JSTestPage(ViewBase):
	@admin_required
	def get(self):
		state = self.request.get('state', 'interval')
		display = self.request.get('display', 'voting')
		votes_used = self.request.get('votes_used', '')
		available_mock = [1,2,3]
		three_options = [{"name": "Walks into a house", "count": 20},
					    {"name": "Something else crazy long, so forget about what you know about options lenghts", "count": 30},
					    {"name": "Here is a super long option that nobody could have ever guessed because they never dreamed of such things", "count": 10}]
		five_options = [{"name": "Option 1", "count": 20},
					   {"name": "Option 2", "count": 50},
					   {"name": "Option 3", "count": 10},
					   {"name": "Option 4", "count": 15},
					   {"name": "Option 5", "count": 5}]
		player_options = [{'photo_filename': 'freddy.jpg', 'count': 30},
		 				  {'photo_filename': 'dan.jpg', 'count': 10},
		 				  {'photo_filename': 'eric.jpg', 'count': 15},
		 				  {'photo_filename': 'brogan.jpg', 'count': 5},
		 				  {'photo_filename': 'camilla.png', 'count': 20},
		 				  {'photo_filename': 'lindsay.png', 'count': 10},
		 				  {'photo_filename': 'greg.jpg', 'count': 5}]
		show_mock = type('Show',
						 (object,),
						 dict(scheduled = get_mountain_time(),
							  player_actions = [],
							  theme = type('Theme', (object,), dict(name = 'Pirates')),
							  is_today = True))
		mock_data = {'state': state, 'display': display}
		if state == 'interval':
			if display == 'voting':
				mock_data.update({'player_name': 'Freddy',
				                  'player_photo': 'freddy.jpg',
				                  'options': three_options})
			else:
				mock_data.update({'player_name': 'Freddy',
				                  'player_photo': 'freddy.jpg',
								  'voted': three_options[1]['name'],
								  'count': three_options[1]['count']})
		elif state == 'test':
			if display == 'voting':
				mock_data.update({'options': five_options})
			else:
				mock_data.update({'voted': five_options[1]['name'],
								  'count': five_options[1]['count']})
		elif state == 'incident':
			if display == 'voting':
				mock_data.update({'options': five_options})
			else:
				mock_data.update({'voted': five_options[1]['name'],
							      'count': five_options[1]['count']})
		elif state in ROLE_TYPES:
			if display == 'voting':
				player_num = int(self.request.get('players', '8'))
				mock_data.update({'role': True,
								  'options': player_options[:player_num]})
			else:
				mock_data.update({'role': True,
								  'voted': state,
							 	  'photo_filename': player_options[0]['photo_filename'],
							 	  'count': player_options[0]['count']})
		
		mock_data['used_types'] = []
		# Add used vote types
		for vt in VOTE_TYPES:
			if vt in votes_used:
				mock_data['used_types'].append(vt)
				setattr(show_mock, vt, True)
		
		# Add start of vote time
		now_tz = back_to_tz(get_mountain_time())
		end_vote_time = now_tz + datetime.timedelta(seconds=VOTE_AFTER_INTERVAL)
		mock_data['hour'] = end_vote_time.hour
		mock_data['minute'] = end_vote_time.minute
		mock_data['second'] = end_vote_time.second
		mock_data['second'] = end_vote_time.second
		mock_data['voting_length'] = (end_vote_time - now_tz).seconds

		context	= {'show': show_mock,
				   'now_tz': back_to_tz(get_mountain_time()),
				   'available_actions': available_mock,
				   'available_items': available_mock,
				   'available_characters': available_mock,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL,
				   'mocked': True,
				   'mock_data': json.dumps(mock_data)}
		self.response.out.write(template.render(self.path('js_test.html'),
												self.add_context(context)))
