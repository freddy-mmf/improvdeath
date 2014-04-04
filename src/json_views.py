import json
import datetime

from google.appengine.ext import ndb

from views_base import ViewBase
from models import (Show, Action, LiveActionVote, Item, WildcardCharacter,
					RoleVote, VOTE_AFTER_INTERVAL, ROLE_AFTER_INTERVAL)
from timezone import get_mountain_time, back_to_tz


ITEM_AMOUNT = 5
WILDCARD_AMOUNT = 5


class CurrentTime(ViewBase):
	def get(self):
		mt = get_mountain_time()
		date_values = {'hour': mt.hour,
					   'minute': mt.minute,
					   'second': mt.second}
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(date_values))


class ShowJSON(ViewBase):
    def get(self, show_id):
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
                                                     'percent': percent})
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
        elif state == 'role':
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
        elif state == 'wildcard':
            # If we're in the voting phase for a wildcard character
            if display == 'voting':
                wcs = WildcardCharacter.query(WildcardCharacter.used == False,
                            ).order(-WildcardCharacter.vote_value).fetch(WILDCARD_AMOUNT)
                response_json['options'] = []
                for wc in wcs:
                    percent = wc.live_vote_percent(show.key)
                    response_json['options'].append({'name': wc.name,
                                                     'id': wc.key.id(),
                                                     'percent': percent})
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
        # If a shapeshifter or lover has been triggered
        elif state == 'shapeshifter' or state == 'lover':
            # If we're in the voting phase for the shapeshifter/lover
            if display == 'voting':
                response_json['options'] = []
                # Loop through all the players in the show
                for player in show.players:
                    player_dict = {'player_name': player.name}
                    # Get the live voting percentage for a shapeshifter/lover
                    change_vote = get_or_create_role_vote(show, player, state)
                    percent = change_vote.live_role_vote_percent
                    player_dict['percent'] = percent
                    response_json['options'].append(player_dict)
            # If we are showing the results of the vote
            elif display == 'result':
                # Set the shapeshifter/lover if it isn't already set
                if not getattr(show, state, None):
                    voted_change = RoleVote.query(RoleVote.role == state,
                                                   RoleVote.show == show.key,
                                    ).order(-RoleVote.live_vote_value,
                                            -RoleVote.vote_value).get()
                    show.voted_change = voted_change.player
                    show.put()
                percent = voted_change.live_role_vote_percent
                change_player = getattr(show, state, None)
                response_json['result'] = {state: change_player.get().name,
                                           'percent': percent}
        
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(action_data))


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