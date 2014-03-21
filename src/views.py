import os
import json
import datetime
import random
import math
from functools import wraps

import webapp2
from webapp2_extras import sessions

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import ndb

from models import (Show, Player, PlayerAction, ShowPlayer, ShowAction, Action,
					Theme, ActionVote, ThemeVote, LiveActionVote, Item, ItemVote,
					LiveItemVote, WildcardCharacter, WildcardCharacterVote,
					LiveWildcardCharacterVote, RoleVote, LiveRoleVote,
					VOTE_AFTER_INTERVAL, ROLE_AFTER_INTERVAL, DISPLAY_VOTED)

from timezone import get_mountain_time, back_to_tz

ITEM_AMOUNT = 5
WILDCARD_AMOUNT = 5


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            redirect_uri = users.create_login_url(webapp2.get_request().uri)
            print redirect_uri
            return webapp2.redirect(redirect_uri, abort=True)
        return func(*args, **kwargs)
    return decorated_view


def get_today_start():
	today = get_mountain_time().date()
	return datetime.datetime.fromordinal(today.toordinal())


def get_tomorrow_start():
	today = get_mountain_time().date()
	tomorrow = today + datetime.timedelta(1)
	return datetime.datetime.fromordinal(tomorrow.toordinal())


def future_show():
	# See if there is a show today, otherwise users aren't allowed to submit actions
	today_start = get_today_start()
	return bool(Show.query(Show.scheduled >= today_start).get())


class ViewBase(webapp2.RequestHandler):
	def __init__(self, *args, **kwargs):
		super(ViewBase, self).__init__(*args, **kwargs)
		self.app = webapp2.get_app()
		user = users.get_current_user()
		if users.get_current_user():
			auth_url = users.create_logout_url(self.request.uri)
			auth_action = 'Logout'
		else:
			auth_url = users.create_login_url(self.request.uri)
			auth_action = 'Login'
		self.context = {
					'host_domain': self.request.host_url.replace('http://', ''),
				    'image_path': self.app.registry.get('images'),
		            'css_path': self.app.registry.get('css'),
		            'js_path': self.app.registry.get('js'),
		            'audio_path': self.app.registry.get('audio'),
		            'player_image_path': self.app.registry.get('player_images'),
		            'is_admin': users.is_current_user_admin(),
					'user': user,
					'auth_url': auth_url,
					'auth_action': auth_action,
					'path_qs': self.request.path_qs}
	
	def add_context(self, add_context={}):
		self.context.update(add_context)
		return self.context
	
	def path(self, filename):
		return os.path.join(self.app.registry.get('templates'), filename)

	def dispatch(self):
		self.session_store = sessions.get_store(request=self.request)
		try:
			webapp2.RequestHandler.dispatch(self)
		finally:
			self.session_store.save_sessions(self.response)

	@webapp2.cached_property
	def session(self):
		session = self.session_store.get_session()
		if not session.get('id'):
			# Get a random has to store as the session id
			session['id'] = random.getrandbits(128)
		return session


class RobotsTXT(webapp2.RequestHandler):
	def get(self):
		# Set to not be indexed
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.out.write("User-agent: *\nDisallow: /")

		
class MainPage(ViewBase):
	def get(self):
		today_start = get_today_start()
		tomorrow_start = get_tomorrow_start()

		# Get the current show
		current_show = Show.query(
			Show.scheduled > today_start,
			Show.scheduled < tomorrow_start).order(-Show.scheduled).get()
		# Get the future shows
		future_shows = Show.query(
			Show.scheduled > tomorrow_start).order(Show.scheduled).filter()
		# Get the previous shows
		previous_shows = Show.query(Show.end_time != None).order(-Show.end_time).filter()
		context = {'current_show': current_show,
				   'future_shows': future_shows,
				   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class ShowPage(ViewBase):
	def get(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		available_actions = len(Action.query(
							   Action.used == False).fetch())
		context	= {'show': show,
				   'available_actions': available_actions,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL,
				   'ROLE_AFTER_INTERVAL': ROLE_AFTER_INTERVAL,
				   'DISPLAY_VOTED': DISPLAY_VOTED}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))

	def post(self, show_key):
		voted = False
		voted_role = None
		show = ndb.Key(Show, int(show_key)).get()
		action_id = self.request.get('action_id')
		player_id = self.request.get('player_id')
		interval = self.request.get('interval')
		item_id = self.request.get('item_id')
		player_role = self.request.get('player_role')
		wildcard_character_id = self.request.get('wildcard_character_id')
		session_id = str(self.session.get('id'))
		
		# Admin is starting the show
		if self.request.get('start_show') and self.context.get('is_admin', False):
			show.start_time = get_mountain_time()
			show.put()
		# Admin is starting item vote
		elif self.request.get('item_vote') and self.context.get('is_admin', False):
			show.item_vote_init = get_mountain_time()
			show.put()
		# Admin is starting role vote
		elif self.request.get('role_vote') and self.context.get('is_admin', False):
			show.role_vote_init = get_mountain_time()
			show.put()
		# Admin is starting wildcard vote
		elif self.request.get('wildcard_vote') and self.context.get('is_admin', False):
			show.wildcard_vote_init = get_mountain_time()
			show.put()
		# Admin is starting the shapeshifter vote
		elif self.request.get('shapeshifter_vote') and self.context.get('is_admin', False):
			show.shapeshifter_vote_init = get_mountain_time()
			show.put()
		# Get submitting an action vote for an interval
		elif action_id and player_id and interval:
			voted = True
			action = ndb.Key(Action, int(action_id))
			player = ndb.Key(Player, int(player_id))
			# If the user hasn't already voted
			if not player.get().get_live_action_vote(interval, session_id):
				LiveActionVote(action=action,
							   player=player,
							   interval=int(interval),
							   created=get_mountain_time().date(),
							   session_id=session_id).put()
		# Submitting an item vote
		elif item_id:
			voted = True
			item = ndb.Key(Item, int(item_id))
			# If the user hasn't already voted for an item
			if not item.get().get_live_item_vote(session_id):
				LiveItemVote(item=item,
							 created=get_mountain_time().date(),
							 session_id=session_id).put()
		# Submitting a player role vote
		elif player_id and player_role:
			voted = True
			player = ndb.Key(Player, int(player_id))
			# If no role vote exists for this user
			if not player.get().get_role_vote(show, player_role):
				# Create an initial Role vote
				role_vote = RoleVote(show=show,
						 			 player=player,
						 			 role=player_role).put()
			# If the user hasn't already submitted a live role vote
			if not role_vote.get().get_live_role_vote(session_id):
				# Create the live role vote
				LiveRoleVote(show=show,
						 	 player=player,
						 	 role=player_role,
						 	 session_id=session_id).put()
		# Submitting a wildcard vote
		elif wildcard_character_id:
			voted = True
			wildcard_character = ndb.Key(WildcardCharacter, int(wildcard_character_id))
			# If the user hasn't already voted for a wildcard character
			if not wildcard_character.get().get_live_wc_vote(session_id):
				# Add the live vote for the wildcard character
				LiveWildcardCharacterVote(wildcard_character=wildcard_character,
							 			  session_id=session_id).put()
						   
		context	= {'show': show,
				   'host_url': self.request.host_url,
				   'VOTE_AFTER_INTERVAL': VOTE_AFTER_INTERVAL,
				   'ROLE_AFTER_INTERVAL': ROLE_AFTER_INTERVAL,
				   'DISPLAY_VOTED': DISPLAY_VOTED,
				   'voted': voted}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))

class CreateShow(ViewBase):
	@admin_required
	def get(self):
		context = {'players': Player.query().fetch()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		length = int(self.request.get('show_length'))
		scheduled_string = self.request.get('scheduled')
		theme = self.request.get('theme')
		player_list = self.request.get_all('player_list')
		action_intervals = self.request.get('action_intervals')
		context = {'players': Player.query().fetch()}
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


class DeleteShows(ViewBase):
	@admin_required
	def get(self):
		context = {'shows': Show.query().fetch()}
		self.response.out.write(template.render(self.path('delete_shows.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		show_id = int(self.request.get('show_id'))
		show = ndb.Key(Show, int(show_id))
		show_actions = ShowAction.query(ShowAction.show == show).fetch()
		for show_action in show_actions:
			action = show_action.player_action.get().action
			if action:
				action.delete()
			show_action.player_action.delete()
			show_action.key.delete()
		show_players = ShowPlayer.query(ShowPlayer.show == show).fetch()
		for show_player in show_players:
			show_player.key.delete()
		show.delete()
		context = {'deleted': True,
				   'shows': Show.query().fetch()}
		self.response.out.write(template.render(self.path('delete_shows.html'),
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


class AddActions(ViewBase):
	def get(self):
		actions = Action.query(
			Action.used == False).order(-Action.vote_value).fetch()
		context = {'actions': actions,
				   'future_show': future_show()}
		self.response.out.write(template.render(self.path('add_actions.html'),
												self.add_context(context)))

	def post(self):
		context = {'future_show': future_show()}
		action = None
		description = self.request.get('description')
		upvote = self.request.get('upvote')
		if description:
			action = Action(description=description).put().get()
			context['created'] = True
		elif upvote:
			action_key = ndb.Key(Action, int(upvote)).get().key
			av = ActionVote.query(
					ActionVote.action == action_key,
					ActionVote.session_id == str(self.session.get('id', '0'))).get()
			if not av:
				ActionVote(action=action_key,
					  	   session_id=str(self.session.get('id'))).put()
		if action:
			context['actions'] = Action.query(Action.used == False,
											  Action.key != action.key,
											  ).order(Action.key, -Action.vote_value).fetch()
			context['actions'].append(action)
		else:
			context['actions'] = Action.query(Action.used == False
											 ).order(-Action.vote_value).fetch()
			
		self.response.out.write(template.render(self.path('add_actions.html'),
												self.add_context(context)))


class AddThemes(ViewBase):
	def get(self):
		themes = Theme.query().order(-Theme.vote_value).fetch()
		context = {'themes': themes}
		self.response.out.write(template.render(self.path('add_themes.html'),
												self.add_context(context)))

	def post(self):
		context = {}
		theme = None
		theme_name = self.request.get('theme_name')
		upvote = self.request.get('upvote')
		if theme_name:
			theme = Theme(name=theme_name,
						  vote_value=0).put().get()
			context['created'] = True
		elif upvote:
			theme_key = ndb.Key(Theme, int(upvote)).get().key
			tv = ThemeVote.query(
					ThemeVote.theme == theme_key,
					ThemeVote.session_id == str(self.session.get('id', '0'))).get()
			if not tv:
				ThemeVote(theme=theme_key,
					  	  session_id=str(self.session.get('id'))).put()
		if theme:
			# Have to sort first by theme key, since we query on it. Dumb...
			themes = Theme.query(Theme.key != theme.key
								).order(Theme.key, -Theme.vote_value).fetch()
			context['themes'] = themes
			context['themes'].append(theme)
		else:
			themes = Theme.query().order(-Theme.vote_value).fetch()
			context['themes'] = themes
			
		self.response.out.write(template.render(self.path('add_themes.html'),
												self.add_context(context)))


class DeleteActions(ViewBase):
	@admin_required
	def get(self):
		actions = Action.query(
			Action.used == False).fetch()
		context = {'actions': actions}
		self.response.out.write(template.render(self.path('delete_actions.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		context = {}
		action_list = self.request.get_all('action_list')
		delete_unused = self.request.get_all('delete_unused')
		if action_list:
			for action in action_list:
				action_entity = ndb.Key(Action, int(action)).get()
				# Get all the related action votes and delete them
				action_votes = ActionVote.query(ActionVote.action == action_entity.key).fetch()
				for av in action_votes:
					av.key.delete()
				action_entity.key.delete()
			context['cur_deleted'] = True
		elif delete_unused:
			unused_actions = Action.query(Action.used == False).fetch()
			for unused in unused_actions:
				# Get all the related action votes and delete them
				action_votes = ActionVote.query(ActionVote.action == unused.key).fetch()
				for av in action_votes:
					av.key.delete()
				# Delete the un-used actions
				unused.key.delete()
			context['unused_deleted'] = True
		context['actions'] = Action.query(
			Action.used == False).fetch()
		self.response.out.write(template.render(self.path('delete_actions.html'),
												self.add_context(context)))


class DeleteThemes(ViewBase):
	@admin_required
	def get(self):
		context = {'themes': Theme.query().fetch()}
		self.response.out.write(template.render(self.path('delete_themes.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		context = {}
		delete_theme_list = self.request.get_all('delete_theme_list')
		if delete_theme_list:
			for theme in delete_theme_list:
				theme_entity = ndb.Key(Theme, int(theme)).get()
				# Get all the related theme votes and delete them
				theme_votes = ThemeVote.query(ThemeVote.theme == theme_entity.key).fetch()
				for tv in theme_votes:
					tv.key.delete()
				theme_entity.key.delete()
			context['cur_deleted'] = True
		context['themes'] = Theme.query().fetch()
		self.response.out.write(template.render(self.path('delete_themes.html'),
												self.add_context(context)))


class ActionsJSON(ViewBase):
	def get(self, show_id, interval):
		show = ndb.Key(Show, int(show_id)).get()
		# Get the player
		player = show.get_player_by_interval(interval)
		# Determine if we've already voted on this interval
		live_vote = player.get().get_live_action_vote(interval, self.session.get('id'))
		now = get_mountain_time()
		# Add timezone for comparisons
		now_tz = back_to_tz(now)
		interval_vote_end = show.start_time_tz + datetime.timedelta(minutes=int(interval)) \
							  + datetime.timedelta(seconds=VOTE_AFTER_INTERVAL)
		if now_tz > interval_vote_end:
			player_action = show.get_player_action_by_interval(interval)
			# If an action wasn't already chosen for this interval
			if not player_action.action:
				# Get the actions that were voted on this interval
				interval_voted_actions = []
				live_action_votes = LiveActionVote.query(
										LiveActionVote.player == player,
										LiveActionVote.interval == int(interval),
										LiveActionVote.created == now.date()).fetch()
				# Add the voted on actions to a list
				for lav in live_action_votes:
					interval_voted_actions.append(lav.action)
				# If the actions were voted on
				if interval_voted_actions:
					# Get the most voted, un-used action
					voted_action = Action.query(
									Action.used == False,
									Action.key.IN(interval_voted_actions),
									).order(-Action.live_vote_value).get()
				# If no live action votes were cast
				# take the highest regular voted action that hasn't been used
				else:
					# Get the most voted, un-used action
					voted_action = Action.query(
									Action.used == False,
									).order(-Action.vote_value).get()
				# Set the player action
				player_action.time_of_action = now
				player_action.action = voted_action.key
				player_action.put()
				# Set the action as used
				voted_action.used = True
				voted_action.put()
				percent = player.get().get_live_action_percentage(voted_action,
											  					  interval,
			  	     											  len(live_action_votes))
				action_data = {'current_action': voted_action.description,
							   'percent': percent}
			else:
				all_votes = player.get().get_all_live_action_count(interval)
				percent = player.get().get_live_action_percentage(player_action.action,
											  					  interval,
											  					  all_votes)
				action_data = {'current_action': player_action.action.get().description,
							   'percent': percent}
		elif not live_vote:
			# Return un-used actions, sorted by vote
			unused_actions = Action.query(Action.used == False,
										  ).order(-Action.vote_value).fetch(3)
			all_votes = player.get().get_all_live_action_count(interval)
			action_data = []
			for i in range(0, 3):
				percent = player.get().get_live_action_percentage(unused_actions[i].key,
											  					  interval,
											  					  all_votes)
				try:
					action_data.append({'name': unused_actions[i].description,
									    'id': unused_actions[i].key.id(),
									    'percent': percent})
				except IndexError:
					pass
		else:
			action_data = {'voted': True}
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(action_data))


class HeroJSON(ViewBase):
	def get(self, show_id, vote_type):
		show = ndb.Key(Show, int(show_id)).get()
		response_json = show.current_vote_state().copy()
		state = response_json.get('state', 'default')
		display = response_json.get('display')
		# If an item has been triggered
		if state == 'item':
			# If we're in the voting phase for an item
			if display == 'voting':
				items = Item.query(Item.used == False,
							).order(-Item.vote_value).fetch(ITEM_AMOUNT)
				response_json['options'] = []
				for item in items:
					percent = item.live_vote_percent(show.key)
					response_json['options'].append({'name': item.name,
								 					 'id': item.key.id(),
							   						 'percent': percent}
			# If we are showing the results of the vote
			elif display == 'result':
				# Set the most voted item if it isn't already set
				if not show.item:
					voted_item = Item.query(Item.used == False,
									).order(-Item.live_vote_value,
											-Item.vote_value).get()
					show.item = voted_item.key
					show.put()
					# Set the item as used
					voted_item.used = True
					voted_item.put()
				percent = show.item.get().live_vote_percent(show.key)
				response_json['result'] = {'name': show.item.get().name,
							   			   'percent': percent}
		# If a role (hero/villain) has been triggered
		if state == 'role':
			# If we're in the voting phase for a role
			if display == 'voting':
				response_json['options'] = []
				# Loop through all the players in the show
				for player in show.players:
					player_dict = {'player_name': player.name}
					# Loop through the hero and villain roles
					for role_name in ['hero', 'villain']:
						# Get the live voting percentage for a role
						role_vote = get_or_create_role_vote(show, player, role_name)
						percent = role_vote.live_role_vote_percent
						player_dict['%s_percent' % role_name] = percent
					response_json['options'].append(player_dict)
			# If we are showing the results of the vote
			elif display == 'result':
				# Set the hero if it isn't already set
				if not show.hero:
					voted_hero = RoleVote.query(RoleVote.role == 'hero',
												   RoleVote.show == show.key,
									).order(-RoleVote.live_vote_value,
											-RoleVote.vote_value).get()
					show.hero = voted_hero.player
					show.put()
				# Set the villain if it isn't already set
				if not show.villain:
					voted_villains = RoleVote.query(RoleVote.role == 'villain',
												   RoleVote.show == show.key,
									).order(-RoleVote.live_vote_value,
											-RoleVote.vote_value).fetch()
					# If the player has already been voted as the hero
					if voted_villains[0].player == show.hero:
						voted_villain = voted_villains[1]
						# Set the next highest voted as the villain
						show.villain = voted_villain.player
					# Otherwise set the player as the villain
					else:
						voted_villain = voted_villains[0]
						show.villain = voted_villain.player
					show.put()
				# Get the voted percentages for the hero/villain
				hero_percent = voted_hero.live_role_vote_percent
				villain_percent = voted_villain.live_role_vote_percent
				response_json['result'] = {'hero': show.villain.get().name,
							   			   'hero_percent': hero_percent,
										   'villain': show.villain.get().name,
							   			   'villain_percent': villain_percent}
		# If an wildcard character has been triggered
		if state == 'wildcard':
			# If we're in the voting phase for a wildcard character
			if display == 'voting':
				wcs = WildcardCharacter.query(WildcardCharacter.used == False,
							).order(-WildcardCharacter.vote_value).fetch(WILDCARD_AMOUNT)
				response_json['options'] = []
				for wc in wcs:
					percent = wc.live_vote_percent(show.key)
					response_json['options'].append({'name': wc.name,
								 					 'id': wc.key.id(),
							   						 'percent': percent}
			# If we are showing the results of the vote
			elif display == 'result':
				# Set the most voted wildcard character if it isn't already set
				if not show.wildcard_character:
					voted_wc = WildcardCharacter.query(WildcardCharacter.used == False,
									).order(-WildcardCharacter.live_vote_value,
											-WildcardCharacter.vote_value).get()
					show.wildcard_character = voted_wc.key
					show.put()
					# Set the wildcard character as used
					voted_wc.used = True
					voted_wc.put()
				percent = show.wildcard_character.get().live_vote_percent(show.key)
				response_json['result'] = {'name': show.wildcard_character.get().name,
							   			   'percent': percent}
		# If a shapeshifter has been triggered
		if state == 'shapeshifter':
			# If we're in the voting phase for the shapeshifter
			if display == 'voting':
				response_json['options'] = []
				# Loop through all the players in the show
				for player in show.players:
					player_dict = {'player_name': player.name}
					# Get the live voting percentage for a shapeshifter
					shapeshifter_vote = get_or_create_role_vote(show,
																player, 
																'shapeshifter')
					percent = shapeshifter_vote.live_role_vote_percent
					player_dict['shapeshifter_percent'] = percent
					response_json['options'].append(player_dict)
			# If we are showing the results of the vote
			elif display == 'result':
				# Set the shapeshifter if it isn't already set
				if not show.shapeshifter:
					voted_shapeshifter = RoleVote.query(RoleVote.role == 'shapeshifter',
												   RoleVote.show == show.key,
									).order(-RoleVote.live_vote_value,
											-RoleVote.vote_value).get()
					show.voted_shapeshifter = voted_shapeshifter.player
					show.put()
				shapeshifter_percent = voted_shapeshifter.live_role_vote_percent
				response_json['result'] = {'shapeshifter': show.shapeshifter.get().name,
							   			   'shapeshifter_percent': shapeshifter_percent}
		
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(action_data))


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
				   'mocked': self.request.GET.get('mock', 'full'),
				   'sample': self.request.GET.get('sample'),
				   'is_admin': self.request.GET.get('is_admin')}
		self.response.out.write(template.render(self.path('js_test.html'),
												self.add_context(context)))
												

class CurrentTime(ViewBase):
	def get(self):
		mt = get_mountain_time()
		date_values = {'hour': mt.hour,
					   'minute': mt.minute,
					   'second': mt.second}
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(date_values))