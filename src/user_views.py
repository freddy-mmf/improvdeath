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


def pre_show_voting_post(type_name, entry_value_type, type_model, type_vote_model,
						 request, session_id, is_admin):
	context = {'session_id': session_id}
	entity = None
	# Get the value of the entry that was added
	entry_value = request.get('entry_value')
	# Get the upvote
	upvote = request.get('upvote')
	# If a delete was requested on an entry
	delete_id = request.get('delete_id')
	# Get the key to query with (i.e. ThemeVote.theme)
	type_vote_key_query = getattr(type_vote_model, type_name, None)
	if entry_value:
		entity_data = {entry_value_type: entry_value,
					   'vote_value': 0,
					   'session_id': session_id}
		entity = type_model(**entity_data).put().get()
		context['created'] = True
	elif upvote:
		entity_key = ndb.Key(type_model, int(upvote)).get().key
		tv = type_vote_model.query(
				type_vote_key_query == entity_key,
				type_vote_model.session_id == session_id).get()
		if not tv:
			vote_data = {type_name: entity_key,
						 'session_id': session_id}
			type_vote_model(**vote_data).put()
	# If a delete was requested
	elif delete_id:
		# Fetch the them
		entity = ndb.Key(type_model, int(delete_id)).get()
		# Make sure the entry was either the session id that created it
		# Or this is an admin user
		if session_id == entity.session_id or is_admin:
			entity.key.delete()
		
	if entity:
		# Have to sort first by entity key, since we query on it. Dumb...
		entities = type_model.query(type_model.used == False,
								  type_model.key != entity.key).fetch()
		entities.sort(key=lambda x: (x.vote_value, x.created), reverse=True)
		# If the entity wasn't deleted
		if not delete_id:
			# Add the newly added entity
			entities.append(entity)
	else:
		entities = type_model.query(type_model.used == False,
								   ).order(-type_model.vote_value,
									 type_model.created).fetch()
	context['%ss' % type_name] = entities
	
	return context


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
			vote_data = show.current_action_options()
		else:
			# Hero
			vote_data = show.current_vote_options(show)
		# If we're in the voting period
		if vote_data.get('display') == 'voting':
			state = vote_data['state']
			try:
				voted_option = vote_data['options'][vote_num]
			except IndexError:
				state = None
		else:
			state = None
		# Submitting an interval vote
		if state == 'interval':
			voted = True
			interval = int(vote_data['interval'])
			action = ndb.Key(Action, int(voted_option['id']))
			player = ndb.Key(Player, int(vote_data['player_id']))
			# If the user hasn't already voted
			if not player.get().get_live_action_vote_exists(show.key, interval, session_id):
				LiveActionVote(action=action,
							   player=player,
							   show=show.key,
							   interval=interval,
							   created=get_mountain_time().date(),
							   session_id=session_id).put()
		# Submitting a player role vote
		elif state in ROLE_TYPES:
			voted = True
			player = ndb.Key(Player, int(voted_option['id']))
			role_vote = player.get().get_role_vote(show, state)
			# If no role vote exists for this user
			if not role_vote:
				# Create an initial Role vote
				role_vote = RoleVote(show=show.key,
						 			 player=player,
						 			 role=state).put()
			else:
				role_vote = role_vote.key
			# If the user hasn't already submitted a live role vote
			if not role_vote.get().get_live_role_vote_exists(show.key, state, session_id):
				# Create the live role vote
				LiveRoleVote(show=show.key,
						 	 player=player,
						 	 role=state,
						 	 session_id=session_id).put()
		# Submitting an incident vote
		elif state == 'incident':
			interval = -1
			voted = True
			action = ndb.Key(Action, int(voted_option['id']))
			# If the user hasn't already voted for the incident
			if not action.get().get_live_action_vote_exists(show.key, interval, session_id):
				LiveActionVote(action=action,
							   show=show.key,
							   player=show.hero,
							   interval=interval,
							   created=get_mountain_time().date(),
							   session_id=session_id).put()
		# Submitting an item vote
		elif state == 'test':
			voted = True
			test = ndb.Key(VotingTest, int(voted_option['id']))
			# If the user hasn't already voted for an item
			if not test.get().get_live_test_vote_exists(show.key, session_id):
				LiveVotingTest(test=test,
							   show=show.key,
							   session_id=session_id).put()
		# Submitting an item vote
		elif state == 'item':
			voted = True
			item = ndb.Key(Item, int(voted_option['id']))
			# If the user hasn't already voted for an item
			if not item.get().get_live_item_vote_exists(show.key, session_id):
				LiveItemVote(item=item,
							 show=show.key,
							 session_id=session_id).put()
		# Submitting a wildcard vote
		elif state == 'wildcard':
			voted = True
			wildcard = ndb.Key(WildcardCharacter, int(voted_option['id']))
			# If the user hasn't already voted for a wildcard character
			if not wildcard.get().get_live_wc_vote_exists(show.key, session_id):
				# Add the live vote for the wildcard character
				LiveWildcardCharacterVote(wildcard=wildcard,
										  show=show.key,
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
				   'show_today': show_today(),
				   'session_id': str(self.session.get('id', '0'))}
		self.response.out.write(template.render(self.path('add_actions.html'),
												self.add_context(context)))

	def post(self):
		context = pre_show_voting_post('action',
									   'description',
									   Action,
									   ActionVote,
									   self.request,
									   str(self.session.get('id', '0')),
									   self.context.get('is_admin', False))
		context['show_today'] = show_today
			
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
		context = {'themes': themes,
				   'session_id': str(self.session.get('id', '0'))}
		self.response.out.write(template.render(self.path('add_themes.html'),
												self.add_context(context)))

	def post(self):
		context = pre_show_voting_post('theme',
									   'name',
									   Theme,
									   ThemeVote,
									   self.request,
									   str(self.session.get('id', '0')),
									   self.context.get('is_admin', False))
			
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