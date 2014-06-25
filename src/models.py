import datetime
import math
import random

from google.appengine.ext import ndb

from timezone import (get_mountain_time, back_to_tz, get_today_start,
                      get_tomorrow_start)

VOTE_AFTER_INTERVAL = 25
DISPLAY_VOTED = 10
WILDCARD_AMOUNT = 5
ITEM_AMOUNT = 5
ROLE_TYPES = ['hero', 'villain', 'shapeshifter', 'lover']
VOTE_TYPES = list(ROLE_TYPES)
VOTE_TYPES += ['incident', 'interval', 'test']
VOTE_OPTIONS = 5
INCIDENT_AMOUNT = 5
ACTION_OPTIONS = 3
RANDOM_ACTION_OPTIONS = 6


def show_today():
	# See if there is a show today, otherwise users aren't allowed to submit actions
	today_start = get_today_start()
	tomorrow_start = get_tomorrow_start()
	return bool(Show.query(Show.scheduled >= today_start,
						   Show.scheduled < tomorrow_start).get())


def get_current_show():
	return Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()


class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    photo_filename = ndb.StringProperty(required=True)
    date_added = ndb.DateTimeProperty()
    
    @property
    def img_path(self):
        return "/static/img/players/%s" % self.photo_filename
    
    def get_live_action_vote_exists(self, show, interval, session_id):
        return bool(LiveActionVote.query(
                    LiveActionVote.interval == int(interval),
                    LiveActionVote.show == show,
                    LiveActionVote.session_id == str(session_id)).get())
    
    def get_role_vote(self, show, role):
        return RoleVote.query(
                    RoleVote.player == self.key,
                    RoleVote.show == show.key,
                    RoleVote.role == role).get()


class Action(ndb.Model):
    description = ndb.StringProperty(required=True)
    created = ndb.DateProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    live_vote_value = ndb.IntegerProperty(default=0)
    session_id = ndb.StringProperty(required=True)
    
    def get_live_action_vote_exists(self, show, interval, session_id):
        return bool(LiveActionVote.query(
                    LiveActionVote.show == show,
                    LiveActionVote.session_id == str(session_id)).get())
    
    @property
    def get_voted_sessions(self):
        avs = ActionVote.query(ActionVote.action == self.key).fetch()
        return [x.session_id for x in avs]
        

    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(Action, self).put(*args, **kwargs)


class Theme(ndb.Model):
    created = ndb.DateTimeProperty(required=True)
    name = ndb.StringProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    session_id = ndb.StringProperty(required=True)
    
    @property
    def get_voted_sessions(self):
        tvs = ThemeVote.query(ThemeVote.theme == self.key).fetch()
        return [x.session_id for x in tvs]
    
    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(Theme, self).put(*args, **kwargs)


class VotingTest(ndb.Model):
    name = ndb.StringProperty(required=True)
    live_vote_value = ndb.IntegerProperty(default=0)
    
    def get_live_test_vote_exists(self, show, session_id):
        return bool(LiveVotingTest.query(
                    LiveVotingTest.show == show,
                    LiveVotingTest.session_id == str(session_id)).get())


class Show(ndb.Model):
    scheduled = ndb.DateTimeProperty()
    theme = ndb.KeyProperty(kind=Theme)
    test_vote_init = ndb.DateTimeProperty()
    interval_vote_init = ndb.DateTimeProperty()
    hero_vote_init = ndb.DateTimeProperty()
    villain_vote_init = ndb.DateTimeProperty()
    incident_vote_init = ndb.DateTimeProperty()
    shapeshifter_vote_init = ndb.DateTimeProperty()
    recap_type = ndb.StringProperty(choices=VOTE_TYPES)
    recap_init = ndb.DateTimeProperty()
    lover_vote_init = ndb.DateTimeProperty()
    current_interval = ndb.IntegerProperty()
    speedup_reached = ndb.BooleanProperty(default=False)
    incident = ndb.KeyProperty(kind=Action)
    test = ndb.KeyProperty(kind=VotingTest)
    hero = ndb.KeyProperty(kind=Player)
    villain = ndb.KeyProperty(kind=Player)
    shapeshifter = ndb.KeyProperty(kind=Player)
    lover = ndb.KeyProperty(kind=Player)
    locked = ndb.BooleanProperty(default=False)
    
    @property
    def scheduled_tz(self):
        return back_to_tz(self.scheduled)
    
    def get_player_action_by_interval(self, interval):
        for pa in self.player_actions:
            if pa.interval == int(interval):
                return pa
        return None
    
    def get_player_by_interval(self, interval):
        pa = self.get_player_action_by_interval(interval)
        if pa:
            return pa.player
        else:
            return None
        
    @property
    def players(self):
        show_players = ShowPlayer.query(ShowPlayer.show == self.key).fetch()
        return [x.player.get() for x in show_players if getattr(x, 'player', None)]
    
    @property
    def player_actions(self):
        action_intervals = ShowAction.query(ShowAction.show == self.key).fetch()
        return [x.player_action.get() for x in action_intervals if getattr(x, 'player_action', None) and x.player_action.get()]
    
    @property
    def sorted_intervals(self):
        return sorted([x.interval for x in self.player_actions])
    
    def get_next_interval(self, interval):
        sorted_intervals = self.sorted_intervals
        # If given an interval
        if interval != None:
            # Loop through the intervals in order
            for i in range(0, len(sorted_intervals)):
                if interval == sorted_intervals[i]:
                    # Get the minutes elapsed between the next interval in the loop
                    # and the current interval in the loop
                    try:
                        return sorted_intervals[i+1]
                    except IndexError:
                        return None
        # Otherwise, assume first interval
        else:
            try:
                return sorted_intervals[0]
            except IndexError:
                return None
        return None

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
    def vote_options(self):
        max_options = max(len(self.players), VOTE_OPTIONS)
        
        return range(0, max_options)
    
    def get_interval_gap(self, interval):
        next_interval = self.get_next_interval(interval)
        # If there is a next interval
        if interval != None and next_interval != None:
            return int(next_interval) - int(interval)
        return None
    
    @property
    def remaining_intervals(self):
        s_intervals = self.sorted_intervals
        if self.current_interval == None:
            return len(s_intervals)
        try:
            interval_index = s_intervals.index(self.current_interval)
        except ValueError:
            return 0
        return len(s_intervals[interval_index:]) - 1
    
    def get_randomized_unused_actions(self, show, interval):
        # Get the stored interval options
        interval_vote_options = IntervalVoteOptions.query(
                                    IntervalVoteOptions.show == show.key,
                                    IntervalVoteOptions.interval == interval).get()
        # If the interval options haven't been generated
        if not interval_vote_options:                    
            # Return un-used action keys, sorted by vote
            unused_keys = Action.query(Action.used == False,
                                 ).order(-Action.vote_value,
                                         Action.created).fetch(RANDOM_ACTION_OPTIONS,
                                                               keys_only=True)
            # Get a randomized sample of the top ACTION_OPTIONS amount of action keys
            random_sample_keys = list(random.sample(set(unused_keys),
                                                    min(ACTION_OPTIONS, len(unused_keys))))
            # Convert the keys into actual entities
            unused_actions = ndb.get_multi(random_sample_keys)
            ivo_create_dict = {'show': show.key, 'interval': interval}
            # Loop through the randomly select unused actions
            for i in range(0, len(unused_actions)):
                ivo_option_num = i + 1
                # Add the option to the create dict
                ivo_create_dict['option_' + str(ivo_option_num)] = unused_actions[i].key
            # Store the interval options
            IntervalVoteOptions(**ivo_create_dict).put()
        else:
            iov_keys = []
            # Loop through and get the stored interval options
            for i in range(1, ACTION_OPTIONS + 1):
                option_key = getattr(interval_vote_options, 'option_' + str(i), None)
                if option_key:
                    iov_keys.append(option_key)
            # Convert the keys into actual entities
            unused_actions = ndb.get_multi(iov_keys)
        return unused_actions    
    
    @property
    def current_vote_state(self):
        state_dict = {'state': 'default', 'display': 'default', 'used_types': []}
        now = get_mountain_time()
        # Get timezone for comparisons
        now_tz = back_to_tz(now)
        # Go through all the vote times to see if they've started
        for vote_type in VOTE_TYPES:
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
                    state_dict.update(
                           {'state': vote_type,
                            'display': 'voting',
                            # Set the end of the voting period
                            'hour': vote_end.hour,
                            'minute': vote_end.minute,
                            'second': vote_end.second,
                            'voting_length': (vote_end - now_tz).seconds})
                elif now_tz >= vote_end and now_tz <= display_end:
                    state_dict.update({'state': vote_type,
                                       'display': 'result',
                                       'hour': vote_end.hour,
                                       'minute': vote_end.minute,
                                       'second': vote_end.second})
        # If we're in a recap state
        if self.recap_init:
            recap_start_tz = back_to_tz(self.recap_init)
            # Get the end of the recap display
            display_end = recap_start_tz + datetime.timedelta(seconds=DISPLAY_VOTED)
            # If we're in the display period of this recap type
            if now_tz >= recap_start_tz and now_tz <= display_end:
                state_dict.update({'state': self.recap_type,
                                   'display': 'result',
                                   'hour': display_end.hour,
                                   'minute': display_end.minute,
                                   'second': display_end.second})
        
        # Get the list of used vote types
        for vt in VOTE_TYPES:
            # If the vote type has been used (and is not an interval)
            if getattr(self, vt, None) and vt != 'interval':
                state_dict['used_types'].append(vt)
                    
        return state_dict

    def current_vote_options(self, show, voting_only=False):
        vote_options = self.current_vote_state.copy()
        state = vote_options.get('state', 'default')
        display = vote_options.get('display')
        # If an test has been triggered
        if state == 'test':
            # If we're in the voting phase for the test
            if display == 'voting':
                vts = VotingTest.query().fetch(ITEM_AMOUNT)
                vote_options['options'] = []
                for vt in vts:
                    vote_options['options'].append({'name': vt.name,
                                                    'id': vt.key.id(),
                                                    'count': vt.live_vote_value})
            # If we are showing the results of the vote
            elif display == 'result' and not voting_only:
                # Set the most voted test if it isn't already set
                if not show.test:
                    voted_test = VotingTest.query().order(
                                             -VotingTest.live_vote_value).get()
                    show.test = voted_test.key
                    show.put()
                    voted_test.put()
                vote_options['voted'] = show.test.get().name
                vote_options['count'] = show.test.get().live_vote_value
        # If an incident has been triggered
        elif state == 'incident':
            # If we're in the voting phase for an incident
            if display == 'voting':
                actions = Action.query(Action.used == False,
                          ).order(-Action.vote_value,
                                  Action.created).fetch(INCIDENT_AMOUNT)
                vote_options['options'] = []
                for action in actions:
                    vote_options['options'].append({'name': action.description,
                                                    'id': action.key.id(),
                                                    'count': action.live_vote_value})
            # If we are showing the results of the vote
            elif display == 'result' and not voting_only:
                # Set the most voted incident if it isn't already set
                if not show.incident:
                    voted_incident = Action.query(Action.used == False,
                                   ).order(-Action.live_vote_value,
                                           -Action.vote_value,
                                           Action.created).get()
                    show.incident = voted_incident.key
                    show.put()
                    # Set the Action as used
                    voted_incident.used = True
                    voted_incident.put()
                vote_options['voted'] = show.incident.get().description
                vote_options['count'] = show.incident.get().live_vote_value
        # If a role vote has been triggered
        elif state in ROLE_TYPES:
            vote_options['role'] = True
            # If we're in the voting phase for the role
            if display == 'voting':
                vote_options['options'] = []
                # Loop through all the players in the show
                for player in show.players:
                    # Make sure the user isn't already the hero/lover/villain
                    if player.key != show.hero and player.key != show.villain \
                        and player.key != show.lover:
                        change_vote = get_or_create_role_vote(show, player, state)
                        player_dict = {'photo_filename': player.photo_filename,
                                       'id': player.key.id(),
                                       'count': change_vote.live_vote_value}
                        vote_options['options'].append(player_dict)
            # If we are showing the results of the vote
            elif display == 'result' and not voting_only:
                role_player = getattr(show, state, None)
                # Set the role if it isn't already set
                if not role_player:
                    role_votes = RoleVote.query(RoleVote.role == state,
                                                RoleVote.show == show.key,
                                     ).order(-RoleVote.live_vote_value).fetch()
                    # Grab the first player
                    for rv in role_votes:
                        # Make sure they aren't already the hero/villain/lover
                        if rv.player != show.hero and rv.player != show.villain \
                            and rv.player != show.lover:
                            # We've found the voted role, break out of the loop
                            voted_role = rv
                            break
                    # Setting role for the show
                    setattr(show, state, voted_role.player)
                    show.put()
                    # Getting the player selected for the role
                    role_player = voted_role.player
                else:
                    voted_role = RoleVote.query(RoleVote.role == state,
                                                RoleVote.show == show.key,
                                                RoleVote.player == role_player).get()
                vote_options['voted'] = state.title()
                vote_options['photo_filename'] = role_player.get().photo_filename
                vote_options['count'] = voted_role.live_vote_value
        # If an interval has been triggered
        elif state == 'interval':
            interval = self.current_interval
            # Get the player
            player = self.get_player_by_interval(interval)
            # Get the player action for this interval
            player_action = self.get_player_action_by_interval(interval)
            # Get the gap between this interval and the next interval
            interval_gap = self.get_interval_gap(interval)
            vote_options.update({'interval': interval,
                                 'player_id': player.id(),
                                 'player_photo': player.get().photo_filename})
            # If this is a 1 minute interval
            if interval_gap == 1:
                vote_options['speedup'] = True
            # If we're in the voting phase for the interval
            if display == 'voting':
                unused_actions = self.get_randomized_unused_actions(show, interval)
                vote_options['options'] = []
                for i in range(0, ACTION_OPTIONS):
                    try:
                        vote_options['options'].append({
                                            'name': unused_actions[i].description,
                                            'id': unused_actions[i].key.id(),
                                            'count': unused_actions[i].live_vote_value})
                    except IndexError:
                        pass
            # If we are showing the results of the vote
            elif display == 'result' and not voting_only:
                # If an action wasn't already chosen for this interval
                if not player_action.action:
                    # Get the actions that were voted on this interval
                    interval_voted_actions = []
                    live_action_votes = LiveActionVote.query(
                                            LiveActionVote.player == player,
                                            LiveActionVote.interval == int(interval),
                                            LiveActionVote.show == show.key).fetch(ACTION_OPTIONS)
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
                    # If a voted action exists
                    if voted_action:
                        # Set the player action
                        player_action.action = voted_action.key
                        player_action.put()
                        # Set the action as used
                        voted_action.used = True
                        voted_action.put()
                        vote_options.update({'voted': voted_action.description,
                                             'count': voted_action.live_vote_value})
                else:
                    vote_options.update({'voted': player_action.action.get().description,
                                         'count': player_action.action.get().live_vote_value})
        return vote_options
    
    def put(self, *args, **kwargs):
        # If a theme was specified, set the theme as used
        if self.theme:
            theme_entity = self.theme.get()
            theme_entity.used = True
            theme_entity.put()
        return super(Show, self).put(*args, **kwargs)


class ShowPlayer(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    player = ndb.KeyProperty(kind=Player, required=True)


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
    show = ndb.KeyProperty(kind=Show, required=True)
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
    action = ndb.KeyProperty(kind=Action)


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


class LiveVotingTest(ndb.Model):
    test = ndb.KeyProperty(kind=VotingTest, required=True)
    show = ndb.KeyProperty(kind=Show, required=True)
    session_id = ndb.StringProperty(required=True)

    def put(self, *args, **kwargs):
        vt = VotingTest.query(VotingTest.key == self.test).get()
        vt.live_vote_value += 1
        vt.put()
        return super(LiveVotingTest, self).put(*args, **kwargs)


def get_or_create_role_vote(show, player, role):
    role_vote = RoleVote.query(RoleVote.show == show.key,
                               RoleVote.player == player.key,
                               RoleVote.role == role).get()
    if not role_vote:
        role_vote = RoleVote(show=show.key,
                             player=player.key,
                             role=role).put().get()
    return role_vote


class RoleVote(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    player = ndb.KeyProperty(kind=Player, required=True)
    role = ndb.StringProperty(required=True, choices=ROLE_TYPES)
    live_vote_value = ndb.IntegerProperty(default=0)

    def get_live_role_vote_exists(self, show, role, session_id):
        return bool(LiveRoleVote.query(
                    LiveRoleVote.show == show,
                    LiveRoleVote.role == role,
                    LiveRoleVote.session_id == str(session_id)).get())


class LiveRoleVote(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    player = ndb.KeyProperty(kind=Player, required=True)
    role = ndb.StringProperty(required=True, choices=ROLE_TYPES)
    session_id = ndb.StringProperty(required=True)

    def put(self, *args, **kwargs):
        role_vote = RoleVote.query(RoleVote.show == self.show,
                                   RoleVote.player == self.player,
                                   RoleVote.role == self.role).get()
        role_vote.live_vote_value += 1
        role_vote.put()
        return super(LiveRoleVote, self).put(*args, **kwargs)

class IntervalVoteOptions(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    interval = ndb.IntegerProperty(required=True)
    option_1 = ndb.KeyProperty(kind=Action)
    option_2 = ndb.KeyProperty(kind=Action)
    option_3 = ndb.KeyProperty(kind=Action)
