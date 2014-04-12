import datetime

from views_base import ViewBase

from google.appengine.ext.webapp import template
from google.appengine.ext import ndb

from models import (Show, Player, Action, Theme, ActionVote, ThemeVote,
					LiveActionVote, Item, ItemVote,
					LiveItemVote, WildcardCharacter, WildcardCharacterVote,
					LiveWildcardCharacterVote, RoleVote, LiveRoleVote,
					VotingTest, LiveVotingTest,
					VOTE_AFTER_INTERVAL, DISPLAY_VOTED, ROLE_TYPES)
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
		# Get the current show
		current_show = Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()
		context = {'current_show': current_show}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class LiveVote(ViewBase):
	def get(self):
		# Get the current show
		show = Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()
		context	= {'show': show}
		self.response.out.write(template.render(self.path('live_vote.html'),
												self.add_context(context)))

	def post(self):
		voted = True
		# Get the current show
		show = Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()
		vote_num = int(self.request.get('vote_num', '0'))
		session_id = str(self.session.get('id'))
		# Determine which show type we're voting for
		if show.running:
			# Interval
			vote_data = show.current_action_options(show)
		else:
			# Hero
			vote_data = show.current_vote_options(show)
		# If we're in the voting period
		if vote_data.get('display') == 'voting':
			state = vote_data['state']
			voted_option = vote_data['options'][vote_num]
		else:
			state = None
		# Submitting an interval vote
		if state == 'interval':
			voted = True
			action = ndb.Key(Action, int(voted_option['id'])).get()
			player = ndb.Key(Player, int(vote_data['player_id'])).get()
			# If the user hasn't already voted
			if not player.get().get_live_action_vote(show, interval, session_id):
				LiveActionVote(action=action,
							   player=player,
							   interval=int(vote_data['interval']),
							   created=get_mountain_time().date(),
							   session_id=session_id).put()
		# Submitting a player role vote
		elif state in ROLE_TYPES:
			voted = True
			player = ndb.Key(Player, int(voted_option['id']))
			# If no role vote exists for this user
			if not player.get().get_role_vote(show, player_role):
				# Create an initial Role vote
				role_vote = RoleVote(show=show,
						 			 player=player,
						 			 role=state).put()
			# If the user hasn't already submitted a live role vote
			if not role_vote.get().get_live_role_vote(session_id):
				# Create the live role vote
				LiveRoleVote(show=show,
						 	 player=player,
						 	 role=state,
						 	 session_id=session_id).put()
		# Submitting an incident vote
		elif state == 'incident':
			voted = True
			action = ndb.Key(Action, int(voted_option['id']))
			# If the user hasn't already voted for the incident
			if not action.get().get_live_action_vote(session_id):
				LiveActionVote(action=action,
							   player=show.hero,
							   interval=-1,
							   created=get_mountain_time().date(),
							   session_id=session_id).put()
		# Submitting an item vote
		elif state == 'test':
			voted = True
			test = ndb.Key(VotingTest, int(voted_option['id']))
			# If the user hasn't already voted for an item
			if not test.get().get_live_test_vote(session_id):
				LiveVotingTest(test=test,
							   session_id=session_id).put()
		# Submitting an item vote
		elif state == 'item':
			voted = True
			item = ndb.Key(Item, int(voted_option['id']))
			# If the user hasn't already voted for an item
			if not item.get().get_live_item_vote(session_id):
				LiveItemVote(item=item,
							 created=get_mountain_time().date(),
							 session_id=session_id).put()
		# Submitting a wildcard vote
		elif state == 'wildcard':
			voted = True
			wildcard = ndb.Key(WildcardCharacter, int(voted_option['id']))
			# If the user hasn't already voted for a wildcard character
			if not wildcard.get().get_live_wc_vote(session_id):
				# Add the live vote for the wildcard character
				LiveWildcardCharacterVote(wildcard=wildcard,
							 			  session_id=session_id).put()
						   
		context	= {'show': show,
				   'vote_options': show.vote_options,
				   'voted': voted}
		self.response.out.write(template.render(self.path('live_vote.html'),
												self.add_context(context)))


class AddActions(ViewBase):
	def get(self):
		actions = Action.query(
			Action.used == False).order(-Action.vote_value,
										Action.created).fetch()
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
											  ).order(Action.key,
											  		  -Action.vote_value,
											  		  Action.created).fetch()
			context['actions'].append(action)
		else:
			context['actions'] = Action.query(Action.used == False
											 ).order(-Action.vote_value,
											 		 Action.created).fetch()
			
		self.response.out.write(template.render(self.path('add_actions.html'),
												self.add_context(context)))


class AddItems(ViewBase):
	def get(self):
		items = Item.query(
			Item.used == False).order(-Item.vote_value,
									  Item.created).fetch()
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
											  ).order(Item.key,
											          -Item.vote_value,
											          Item.created).fetch()
			context['items'].append(item)
		else:
			context['items'] = Item.query(Item.used == False
											 ).order(-Item.vote_value,
											         Item.created).fetch()
			
		self.response.out.write(template.render(self.path('add_items.html'),
												self.add_context(context)))


class AddCharacters(ViewBase):
	def get(self):
		characters = WildcardCharacter.query(
			WildcardCharacter.used == False).order(-WildcardCharacter.vote_value,
			                                       WildcardCharacter.created).fetch()
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
					WildcardCharacterVote.wildcard == character_key,
					WildcardCharacterVote.session_id == str(self.session.get('id', '0'))).get()
			if not av:
				WildcardCharacterVote(wildcard=character_key,
					  	   session_id=str(self.session.get('id'))).put()
		if character:
			context['characters'] = WildcardCharacter.query(
							       WildcardCharacter.used == False,
								   WildcardCharacter.key != character.key,
								   ).order(WildcardCharacter.key,
								           -WildcardCharacter.vote_value,
								           WildcardCharacter.created).fetch()
			context['characters'].append(character)
		else:
			context['characters'] = WildcardCharacter.query(WildcardCharacter.used == False
											 ).order(-WildcardCharacter.vote_value,
											         WildcardCharacter.created).fetch()
			
		self.response.out.write(template.render(self.path('add_characters.html'),
												self.add_context(context)))


class AddThemes(ViewBase):
	def get(self):
		themes = Theme.query(
					Theme.used == False).order(-Theme.vote_value,
											   Theme.created).fetch()
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
								).order(Theme.key,
										-Theme.vote_value,
										Theme.created).fetch()
			context['themes'] = themes
			context['themes'].append(theme)
		else:
			themes = Theme.query().order(-Theme.vote_value,
										 Theme.created).fetch()
			context['themes'] = themes
			
		self.response.out.write(template.render(self.path('add_themes.html'),
												self.add_context(context)))


class OtherShows(ViewBase):
	def get(self, show_id=None):
		# If a show was specified
		if show_id:
			show = ndb.Key(Show, int(show_id)).get()
			context = {'show': show}
		else:
			tomorrow_start = get_tomorrow_start()
			# Get the future shows
			future_shows = Show.query(
				Show.scheduled > tomorrow_start).order(Show.scheduled).filter()
			# Get the previous shows
			previous_shows = Show.query(
								Show.end_time != None).order(
									-Show.end_time).filter()
			context = {'future_shows': future_shows,
					   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('other_shows.html'),
												self.add_context(context)))