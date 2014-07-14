import datetime
import json
from functools import wraps
import random

import webapp2
from google.appengine.ext.webapp import template
from google.appengine.ext import ndb
from google.appengine.api import users

from views_base import ViewBase

from service import (get_current_show, get_suggestion, get_player, get_show,
					 get_vote_type, fetch_suggestions, get_suggestion_pool,
					 fetch_players, fetch_preshow_votes, fetch_vote_options,
					 fetch_shows, fetch_live_votes, fetch_suggestion_pools,
					 fetch_vote_types, fetch_voted_items, create_show,
					 create_showinterval, create_suggestion_pool,
					 create_vote_type, get_unused_suggestions,
					 reset_live_votes, VOTE_STYLE, OCCURS_TYPE)
from timezone import get_mountain_time, back_to_tz


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            redirect_uri = users.create_login_url(webapp2.get_request().uri)
            return webapp2.redirect(redirect_uri, abort=True)
        return func(*args, **kwargs)
    return decorated_view


class ShowPage(ViewBase):
	@admin_required
	def get(self, show_id):
		show = get_show(key_id=show_id)
		# Determine the available suggestions for live vote types
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
		if self.request.get('vote_start') and self.context.get('is_admin', False):
			pool_type = get_pool_type(name=self.request.get('vote_start'))
			show_pool = get_show_pool(show=show, pool_type=pool_type)
			# Set the current pool type for the show
			show.current_pool_type = pool_type
			# Set the start time of the current vote
			show.current_vote_init = get_mountain_time()
			# If this suggestion pool has intervals
			if vote_type.has_intervals:
				# Get the next interval
				next_interval = pool_type.get_next_interval(show_pool.current_interval)
				# If there is a next interval
				if next_interval != None:
					# Set the current interval to the next interval
					show_pool.current_interval = next_interval
			# Reset all suggestions that haven't been used
			# but have a live_vote_value, to zero
			reset_live_votes()
			# Save the show's new current state
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
		# Admin is showing the leaderboard
		elif self.request.get('show_leaderboard') and self.context.get('is_admin', False):
			show.showing_leaderboard = True
			show.put()
		# Admin is hiding the leaderboard
		elif self.request.get('hide_leaderboard') and self.context.get('is_admin', False):
			show.showing_leaderboard = False
			show.put()
		# Determine the available suggestions for live vote types
		
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
		context = {'vote_types': fetch_vote_types(),
				   'players': fetch_players()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		player_list = self.request.get_all('player_list')
		vote_type_list = self.request.get_all('vote_type_list')
		context = {'vote_types': fetch_vote_types(),
				   'players': fetch_players()}
		if player_list:
			show = create_show()
			# Add the vote types to the show
			for vote_type_id in vote_type_list:
				# Get the vote type from the db
				vote_type = get_vote_type(key_id=vote_type_id)
				# Add the vote type to the show
				show.vote_types.append(vote_type)
				# Get the maximum voting options from the vote type
				# And store it if it's greater than the show's current vote options
				show.vote_options = max(show.vote_options, vote_type.options)
				# If the vote type has intervals
				if vote_type.has_intervals:				
					# If this suggestion vote has players attached
					if vote_type.uses_players:
						# Make a copy of the list of players and randomize it
						rand_players = list(show.players)
						random.shuffle(rand_players, random.random)
						# Add the intervals to the show
						for interval in vote_type.intervals:
							# If random players list gets empty, refill it with more players
							if len(rand_players) == 0:
								rand_players = list(show.players)
								random.shuffle(rand_players, random.random)
							# Pop a random player off the list and create a ShowInterval
							create_showinterval(show=show,
												player=rand_players.pop(),
												interval=interval,
												vote_type=vote_type)
					else:
						# Add the suggestion intervals to the show
						for interval in vote_type.intervals:
							# Create a ShowInterval
							create_showinterval(show=show,
												interval=interval,
												vote_type=vote_type)
			# Add the players to the show
			for player in player_list:
				player_key = get_player(key_id=player)
				show.players.append(player_key)
				show.player_pool.append(player_key)
			# Save changes to the show
			show.put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))


def add_pool_type_context(context):
	# Get all the live pool types that use suggestions
	pool_types = fetch_pool_types(uses_suggestions=True)
	# All available pool types that use suggestions are offered up for deletion
	for pool_type in pool_types:
		context['pools'][pool_type] = fetch_suggestions(pool_type=pool_type,
														used=False)
	return context


class VoteTypes(ViewBase):
	@admin_required
	def get(self):
		context = context = {'vote_types': fetch_vote_types(),
							 'suggestion_pools': fetch_suggestion_pools(),
							 'vote_styles': VOTE_STYLE,
							 'occurs_types': OCCURS_TYPE}
		self.response.out.write(template.render(self.path('vote_types.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		action = None
		vote_type_ids = self.request.get('vote_type_ids')
		# Delete selected vote types
		if vote_type_ids:
			for vote_type_id in vote_type_ids:
				vote_type_entity = get_vote_type(key_id=vote_type_id)
				vote_type_entity.key.delete()
			action = 'deleted'
		# Create Suggestion pool
		elif self.request.get('name'):
			suggestion_pool_id = self.request.get('suggestion_pool_id')
			suggestion_pool = get_suggestion_pool(key_id=suggestion_pool_id)
			intervals_string = self.request.get('interval_list')
			# Get the integer list of interval times
			try:
				intervals = [int(x.strip()) for x in intervals_string.split(',')]
			except ValueError:
				raise ValueError("Invalid interval list '%s'. Must be comma separated.")
			# Create the vote type
			create_vote_type({'name': self.request.get('name'),
							  'display_name': self.request.get('display_name'),
							  'suggestion_pool': suggestion_pool,
							  'preshow_voted': bool(self.request.get('preshow_voted', False)),
							  'has_intervals': bool(self.request.get('has_intervals', False)),
							  'style': self.request.get('style'),
							  'occurs': self.request.get('occurs'),
							  'ordering': self.request.get('ordering'),
							  'options': self.request.get('options'),
							  'randomize_amount': self.request.get('randomize_amount'),
							  'intervals': intervals,
							  })
			action = 'created'
		context = context = {'vote_types': fetch_vote_types(),
							 'suggestion_pools': fetch_suggestion_pools(),
							 'vote_styles': VOTE_STYLE,
							 'occurs_types': OCCURS_TYPE,
							 'action': action}
		self.response.out.write(template.render(self.path('vote_types.html'),
												self.add_context(context)))


class SuggestionPools(ViewBase):
	@admin_required
	def get(self):
		context = {'suggestion_pools': fetch_suggestion_pools()}
		self.response.out.write(template.render(self.path('suggestion_pools.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		action = None
		suggestion_pool_ids = self.request.get('suggestion_pool_ids')
		# Delete selected suggestion pools
		if suggestion_pool_ids:
			for suggestion_pool_id in suggestion_pool_ids:
				suggestion_pool_entity = get_suggestion_pool(key_id=suggestion_pool_id)
				suggestion_pool_entity.key.delete()
			action = 'deleted'
		# Create Suggestion pool
		elif self.request.get('name'):
			create_suggestion_pool({'name': self.request.get('name'),
									'display_name': self.request.get('display_name'),
									'description': self.request.get('description')})
			action = 'created'
		context = {'suggestion_pools': fetch_suggestion_pools(),
				   'action': action}
		self.response.out.write(template.render(self.path('suggestion_pools.html'),
												self.add_context(context)))


class DeleteTools(ViewBase):
	@admin_required
	def get(self):
		context = {'shows': fetch_shows(),
				   'vote_types': get_unused_suggestions()}
		context = add_pool_type_context(context)
		self.response.out.write(template.render(self.path('delete_tools.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		deleted = None
		unused_deleted = False
		show_list = self.request.get_all('show_list')
		suggestion_list = self.request.get_all('suggestion_list')
		delete_unused = self.request.get_all('delete_unused')
		# If suggestion(s) were deleted (archived)
		if suggestion_list:
			for suggestion in suggestion_list:
				suggestion_entity = get_suggestion(key_id=suggestion)
				# Get all the related preshow votes and delete them
				preshow_votes = fetch_preshow_votes(suggestion=suggestion_entity.key)
				for pv in preshow_votes:
					pv.key.delete()
				# Archive the suggestion
				suggestion_entity.archived = True
				suggestion_entity.put()
			deleted = 'Suggestion(s)'
		# If show(s) were deleted
		if show_list:
			for show in show_list:
				show_entity = get_show(key_id=show)
				# Delete the Vote Options attached to the show
				vote_options = fetch_vote_options(show=show_entity.key)
				for vote_option in vote_options:
					vote_option.key.delete()
				# Delete the Suggestions used in the show
				suggestions = fetch_suggestions(show=show_entity.key)
				for suggestion in suggestions:
					suggestion.key.delete()
				# Delete the Preshow Votes used in the show
				preshow_votes = fetch_preshow_votes(show=show_entity.key)
				for preshow_vote in preshow_votes:
					preshow_votes.key.delete()
				# Delete the Live Votes used in the show
				live_votes = fetch_live_votes(show=show_entity.key)
				for live_vote in live_votes:
					live_vote.key.delete()
				# Delete the Voted Items used in the show
				voted_items = fetch_voted_items(show=show_entity.key)
				for voted_item in voted_items:
					voted_item.key.delete()
				# Delete the Show Player Interval used in the show
				showplayerintervals = fetch_showplayerinterval(show=show_entity.key)
				for showplayerinterval in showplayerintervals:
					showplayerinterval.key.delete()
				show_entity.key.delete()
				deleted = 'Show(s)'
		# Delete ALL un-used things
		if delete_unused:
			# Fetch all the suggestions that weren't voted on or used
			suggestions = fetch_suggestions(used=False,
											voted_on=False)
			for suggestion in suggestions:
				# Delete the Preshow Votes used in the show
				preshow_votes = fetch_preshow_votes(suggestion=suggestion.key)
				for preshow_vote in preshow_votes:
					preshow_votes.key.delete()
				# Delete the Live Votes used in the show
				live_votes = fetch_live_votes(suggestion=suggestion.key)
				for live_vote in live_votes:
					live_vote.key.delete()
				suggestion.key.delete()
			deleted = 'All Un-used Actions'
		context = {'deleted': deleted,
				   'unused_deleted': unused_deleted,
				   'shows': fetch_shows(),
				   'vote_types': get_unused_suggestions()}
		context = add_pool_type_context(context)
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
						 dict(player_actions = [],
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
