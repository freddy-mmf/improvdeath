import datetime

from views_base import ViewBase

from google.appengine.ext.webapp import template
from google.appengine.ext import ndb

from models import (Show, Player, Action, Theme, ActionVote, ThemeVote,
					LiveActionVote, Item, ItemVote,
					LiveItemVote, WildcardCharacter, WildcardCharacterVote,
					LiveWildcardCharacterVote, RoleVote, LiveRoleVote,
					VOTE_AFTER_INTERVAL, ROLE_AFTER_INTERVAL, DISPLAY_VOTED)
from timezone import get_mountain_time


def get_today_start():
	today = get_mountain_time().date()
	return datetime.datetime.fromordinal(today.toordinal())


def get_tomorrow_start():
	today = get_mountain_time().date()
	tomorrow = today + datetime.timedelta(1)
	return datetime.datetime.fromordinal(tomorrow.toordinal())


def show_today():
	# See if there is a show today, otherwise users aren't allowed to submit actions
	today_start = get_today_start()
	tomorrow_start = get_tomorrow_start()
	return bool(Show.query(Show.scheduled >= today_start,
						   Show.scheduled < tomorrow_start).get())


class MainPage(ViewBase):
	def get(self):
		today_start = get_today_start()
		tomorrow_start = get_tomorrow_start()

		# Get the current show
		current_show = Show.query(
			Show.scheduled >= today_start,
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


class AddActions(ViewBase):
	def get(self):
		actions = Action.query(
			Action.used == False).order(-Action.vote_value).fetch()
		context = {'actions': actions,
				   'show_today': show_today()}
		self.response.out.write(template.render(self.path('add_actions.html'),
												self.add_context(context)))

	def post(self):
		context = {'show_today': show_today()}
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


class AddItems(ViewBase):
	def get(self):
		items = Item.query(
			Item.used == False).order(-Item.vote_value).fetch()
		context = {'items': items,
				   'show_today': show_today()}
		self.response.out.write(template.render(self.path('add_items.html'),
												self.add_context(context)))

	def post(self):
		context = {'show_today': show_today()}
		item = None
		name = self.request.get('name')
		upvote = self.request.get('upvote')
		if name:
			item = Item(name=name).put().get()
			context['created'] = True
		elif upvote:
			item_key = ndb.Key(Item, int(upvote)).get().key
			av = ItemVote.query(
					ItemVote.item == item_key,
					ItemVote.session_id == str(self.session.get('id', '0'))).get()
			if not av:
				ItemVote(item=item_key,
					  	   session_id=str(self.session.get('id'))).put()
		if item:
			context['items'] = Item.query(Item.used == False,
											  Item.key != item.key,
											  ).order(Item.key, -Item.vote_value).fetch()
			context['items'].append(item)
		else:
			context['items'] = Item.query(Item.used == False
											 ).order(-Item.vote_value).fetch()
			
		self.response.out.write(template.render(self.path('add_items.html'),
												self.add_context(context)))


class AddCharacters(ViewBase):
	def get(self):
		characters = WildcardCharacter.query(
			WildcardCharacter.used == False).order(-WildcardCharacter.vote_value).fetch()
		context = {'characters': characters,
				   'show_today': show_today()}
		self.response.out.write(template.render(self.path('add_characters.html'),
												self.add_context(context)))

	def post(self):
		context = {'show_today': show_today()}
		character = None
		name = self.request.get('name')
		upvote = self.request.get('upvote')
		if name:
			character = WildcardCharacter(name=name).put().get()
			context['created'] = True
		elif upvote:
			character_key = ndb.Key(WildcardCharacter, int(upvote)).get().key
			av = WildcardCharacterVote.query(
					WildcardCharacterVote.wildcard_character == character_key,
					WildcardCharacterVote.session_id == str(self.session.get('id', '0'))).get()
			if not av:
				WildcardCharacterVote(wildcard_character=character_key,
					  	   session_id=str(self.session.get('id'))).put()
		if character:
			context['characters'] = WildcardCharacter.query(
							       WildcardCharacter.used == False,
								   WildcardCharacter.key != character.key,
								   ).order(WildcardCharacter.key,
								           -WildcardCharacter.vote_value).fetch()
			context['characters'].append(character)
		else:
			context['characters'] = WildcardCharacter.query(WildcardCharacter.used == False
											 ).order(-WildcardCharacter.vote_value).fetch()
			
		self.response.out.write(template.render(self.path('add_characters.html'),
												self.add_context(context)))


class AddThemes(ViewBase):
	def get(self):
		themes = Theme.query(
					Theme.used == False).order(-Theme.vote_value).fetch()
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


class OtherShows(ViewBase):
	def get(self):
		tomorrow_start = get_tomorrow_start()
		# Get the future shows
		future_shows = Show.query(
			Show.scheduled > tomorrow_start).order(Show.scheduled).filter()
		# Get the previous shows
		previous_shows = Show.query(Show.end_time != None).order(-Show.end_time).filter()
		context = {'future_shows': future_shows,
				   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('other_shows.html'),
												self.add_context(context)))