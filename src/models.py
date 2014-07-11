import datetime
import math
import random

from google.appengine.ext import ndb

from timezone import (get_mountain_time, back_to_tz, get_today_start,
                      get_tomorrow_start)

VOTE_AFTER_INTERVAL = 25
DISPLAY_VOTED = 10

ROLE_TYPES = ['hero', 'villain', 'shapeshifter', 'lover']
VOTE_TYPES = list(ROLE_TYPES)
VOTE_TYPES += ['incident', 'interval', 'test']

VOTE_STYLE = ['players-only', 'removable-players', 'player-options', 'options']
OCCURS_TYPE = ['before', 'during']


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



class PoolType(ndb.Model):
    name = ndb.StringProperty(required=True)
    display_name = ndb.StringProperty(required=True)
    allows_intervals = ndb.BooleanProperty(default=False)
    uses_suggestions = ndb.BooleanProperty(default=False)
    uses_players = ndb.BooleanProperty(default=False)
    intervals = ndb.IntegerProperty(repeated=True)
    style = ndb.StringProperty(choices=VOTE_STYLE)
    occurs = ndb.StringProperty(choices=OCCURS_TYPE)
    ordering = ndb.IntegerProperty(default=0)
    options = ndb.IntegerProperty(default=3)
    randomize_amount = ndb.IntegerProperty(default=6)
    
    created = ndb.DateProperty(required=True)
    
    def put(self, *args, **kwargs):
        if not self.created:
            self.created = get_mountain_time()
        return super(PoolType, self).put(*args, **kwargs)


class VoteOptions(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    pool_type = ndb.KeyProperty(kind=PoolType, required=True)
    interval = ndb.IntegerProperty()
    option_list = ndb.KeyProperty(kind=Suggestion, repeated=True)


class Suggestion(ndb.Model):
    show = ndb.KeyProperty(kind=Show)
    pool_type = ndb.KeyProperty(kind=PoolType)
    used = ndb.BooleanProperty(default=False)
    voted_on = ndb.BooleanProperty(default=False)
    archived = ndb.BooleanProperty(default=False)
    value = ndb.StringProperty(required=True)
    # Pre-show upvotes
    preshow_value = ndb.IntegerProperty(default=0)
    # Aggregate of current live vote value, gets reset after each vote ends
    live_value = ndb.IntegerProperty(default=0)
    session_id = ndb.StringProperty(required=True)
    user = ndb.UserProperty(default=None)
    
    created = ndb.DateProperty()
    
    def clear_live_votes(self):
        """Delete all the live votes for this suggestion"""
        self.live_value = 0
        self.put()
    
    def get_live_vote_exists(self, show, session_id):
        """Determine if a live vote exists for this suggestion by this session"""
        return bool(LiveVote.query(
                    LiveVote.show == show,
                    LiveVote.session_id == str(session_id)).get())
    
    @property
    def get_voted_sessions(self):
        """Determine which sessions have voted for this suggestion pre-show"""
        psv = PreshowVote.query(PreshowVote.suggestion == self.key).fetch()
        return [x.session_id for x in psv]
        

    def put(self, *args, **kwargs):
        if not self.created:
            self.created = get_mountain_time()
        return super(Suggestion, self).put(*args, **kwargs)


class PreshowVote(ndb.Model):
    show = ndb.KeyProperty(kind=Show)
    suggestion = ndb.KeyProperty(kind=Suggestion, required=True)
    session_id = ndb.StringProperty(required=True)
    user = ndb.UserProperty(default=None)


class LiveVote(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    suggestion = ndb.KeyProperty(kind=Suggestion, required=True)
    session_id = ndb.StringProperty(required=True)
    user = ndb.UserProperty(default=None)
    
    
    def put(self, *args, **kwargs):
        """Increment the Suggestion's live value"""
        suggestion_entity = self.suggestion.get()
        suggestion_entity.live_value += 1
        suggestion_entity.voted_on = True
        suggestion_entity.put()
        return super(LiveVote, self).put(*args, **kwargs)


class VotedItem(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    pool_type = ndb.KeyProperty(kind=PoolType, required=True)
    suggestion = ndb.KeyProperty(kind=Suggestion, required=True)
    interval = ndb.IntegerProperty()


class Show(ndb.Model):
    vote_length = ndb.IntegerProperty(default=25)
    result_length = ndb.IntegerProperty(default=10)
    minimum_vote_options = ndb.IntegerProperty(default=5)
    theme = ndb.KeyProperty(kind=Suggestion)
    current_pool_type = ndb.KeyProperty(kind=PoolType)
    current_vote_init = ndb.DateTimeProperty()
    recap_type = ndb.KeyProperty(kind=PoolType)
    recap_init = ndb.DateTimeProperty()
    players = ndb.KeyProperty(kind=Player, repeated=True)
    locked = ndb.BooleanProperty(default=False)
    showing_leaderboard = ndb.BooleanProperty(default=False)
    
    created = ndb.DateTimeProperty(required=True)
    timezone = ndb.StringProperty(default='America/Denver')
    
    @property
    def pool_types(self):
        return PoolType.query(
            PoolType.live == True,
            PoolType.occurs == 'during').order(PoolType.ordering).fetch()
    
    def get_player_by_interval(self, interval):
        for pi in self.player_intervals:
            if pi.interval == int(interval):
                return pa
        return None
    
    def get_player_by_interval(self, interval):
        pa = self.get_player_action_by_interval(interval)
        if pa:
            return pa.player
        else:
            return None
    
    @property
    def player_intervals(self):
        return [x.player_action.get() for x in self.intervals if getattr(x, 'player_action', None) and x.player_action.get()]
    
    def get_next_interval(self, interval):
        intervals = self.intervals
        # If given an interval
        if interval != None:
            # Loop through the intervals in order
            for i in range(0, len(intervals)):
                if interval == intervals[i]:
                    # Get the minutes elapsed between the next interval in the loop
                    # and the current interval in the loop
                    try:
                        return intervals[i+1]
                    except IndexError:
                        return None
        # Otherwise, assume first interval
        else:
            try:
                return intervals[0]
            except IndexError:
                return None
        return None

    @property
    def is_today(self):
        return self.created.date() == get_mountain_time().date()
    
    @property
    def vote_options(self):
        max_options = max(len(self.players), self.minimum_vote_options)
        return range(0, max_options)
    
    def get_interval_gap(self, interval):
        next_interval = self.get_next_interval(interval)
        # If there is a next interval
        if interval != None and next_interval != None:
            return int(next_interval) - int(interval)
        return None
    
    @property
    def remaining_intervals(self):
        if self.current_interval == None:
            return len(self.intervals)
        try:
            interval_index = self.intervals.index(self.current_interval)
        except ValueError:
            return 0
        return len(self.intervals[interval_index:]) - 1
    
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
                    voted_action = None
                    # Get the actions that were voted on this interval
                    unused_actions = self.get_randomized_unused_actions(show, interval)
                    # Take the action with the highest live_vote_value
                    # Or just default to the first action
                    for action in unused_actions:
                        if voted_action == None:
                            voted_action = action
                        elif action.live_vote_value > voted_action.live_vote_value:
                            voted_action = action
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
        # If created wasn't specified yet
        if no self.created:
            self.created = get_mountain_time()
        # If a theme was specified, set the theme as used
        if self.theme:
            theme_entity = self.theme.get()
            theme_entity.used = True
            theme_entity.put()
        return super(Show, self).put(*args, **kwargs)


class ShowInterval(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    pool_type = ndb.KeyProperty(kind=PoolType, required=True)
    player = ndb.KeyProperty(kind=Player, required=True)
    interval = ndb.IntegerProperty(required=True)


class ShowPool(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    pool_type = ndb.KeyProperty(kind=PoolType, required=True)
    current_interval = ndb.IntegerProperty()
    speedup_reached = ndb.BooleanProperty(default=False)
