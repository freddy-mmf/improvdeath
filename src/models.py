import datetime
import math
import random

from google.appengine.ext import ndb

from timezone import (get_mountain_time, back_to_tz, get_today_start,
                      get_tomorrow_start)

VOTE_AFTER_INTERVAL = 25
DISPLAY_VOTED = 10

VOTE_STYLE = ['all-players', 'player-pool', 'player-options', 'options',
              'preshow-voted']
OCCURS_TYPE = ['before', 'during']


def get_current_show():
	return Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()


class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    photo_filename = ndb.StringProperty(required=True, indexed=False)
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


class SuggestionPool(ndb.Model):
    name = ndb.StringProperty(required=True)
    display_name = ndb.StringProperty(required=True, indexed=False)
    description = ndb.TextProperty(required=True, indexed=False)
    
    created = ndb.DateProperty(required=True)
    
    def put(self, *args, **kwargs):
        if not self.created:
            self.created = get_mountain_time()
        return super(SuggestionPool, self).put(*args, **kwargs)


class Suggestion(ndb.Model):
    show = ndb.KeyProperty(kind=Show)
    suggestion_pool = ndb.KeyProperty(kind=SuggestionPool)
    used = ndb.BooleanProperty(default=False)
    voted_on = ndb.BooleanProperty(default=False)
    archived = ndb.BooleanProperty(default=False)
    value = ndb.StringProperty(required=True, indexed=False)
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
    vote_type = ndb.KeyProperty(kind=VoteType, required=True)
    player = ndb.KeyProperty(kind=Player)
    suggestion = ndb.KeyProperty(kind=Suggestion)
    interval = ndb.IntegerProperty()
    session_id = ndb.StringProperty(required=True)
    user = ndb.UserProperty(default=None)
    
    def put(self, *args, **kwargs):
        """Increment the Suggestion's live value"""
        if self.suggestion:
            suggestion_entity = self.suggestion.get()
            suggestion_entity.live_value += 1
            suggestion_entity.voted_on = True
            suggestion_entity.put()
        return super(LiveVote, self).put(*args, **kwargs)


def vote_type_name_validator(prop, value):
    """Make sure the name field is unique"""
    if VoteType.query(VoteType.name == value).count() > 0:
        raise ValueError("Vote Type name already exists!")
    return None


class VoteType(ndb.Model):
    name = ndb.StringProperty(required=True, validator=vote_type_name_validator)
    display_name = ndb.StringProperty(required=True, indexed=False)
    suggestion_pool = ndb.KeyProperty(kind=SuggestionPool, indexed=False)
    preshow_voted = ndb.BooleanProperty(required=True, default=False, indexed=False)
    has_intervals = ndb.BooleanProperty(required=True, default=False, indexed=False)
    current_interval = ndb.IntegerProperty(indexed=False)
    intervals = ndb.IntegerProperty(repeated=True, indexed=False)
    style = ndb.StringProperty(choices=VOTE_STYLE)
    occurs = ndb.StringProperty(choices=OCCURS_TYPE)
    ordering = ndb.IntegerProperty(default=0)
    options = ndb.IntegerProperty(default=3, indexed=False)
    randomize_amount = ndb.IntegerProperty(default=6, indexed=False)

    def get_next_interval(self, interval):
        # If given an interval
        if interval != None:
            # Loop through the intervals in order
            for i in range(0, len(self.intervals)):
                if interval == self.intervals[i]:
                    # Get the minutes elapsed between the next interval in the loop
                    # and the current interval in the loop
                    try:
                        return self.intervals[i+1]
                    except IndexError:
                        return None
        # Otherwise, assume first interval
        else:
            try:
                return self.intervals[0]
            except IndexError:
                return None
        return None
    
    def get_interval_gap(self, interval):
        next_interval = self.get_next_interval(interval)
        # If there is a next interval
        if interval != None and next_interval != None:
            return int(next_interval) - int(interval)
        return None
    
    @property
    def remaining_intervals(self):
        show = get_current_show()
        # If there's a show today
        if show:
            if self.current_interval == None:
                return len(self.intervals)
            try:
                interval_index = self.intervals.index(self.current_interval)
            except ValueError:
                return 0
            return len(self.intervals[interval_index:]) - 1
        return 0
    
    @property
    def current_voted_item(self):
        return VotedItem.query(VotedItem.vote_type == self.key,
                               VotedItem.interval == self.current_interval).get()
    
    def get_randomized_unused_suggestions(self, show, interval=None):
        # Get the stored interval options
        interval_vote_options = VoteOptions.query(
                                    VoteOptions.vote_type == self.key,
                                    VoteOptions.show == show,
                                    VoteOptions.interval == interval).get()
        # If the interval options haven't been generated
        if not interval_vote_options:                    
            # Return un-used suggestion keys, sorted by vote
            unused_suggestion_keys = Suggestion.query(
                                         Suggestion.suggestion_pool == self.suggestion_pool,
                                         Suggestion.used == False,
                                             ).order(-Suggestion.vote_value,
                                                     Suggestion.created
                                                        ).fetch(self.randomize_amount,
                                                                keys_only=True)
            # Get a randomized sample of the top "option" amount of suggestion keys
            random_sample_keys = list(
                                     random.sample(
                                        set(unused_suggestion_keys),
                                        min(self.options, len(unused_suggestion_keys))))
            # Convert the keys into actual entities
            unused_suggestions = ndb.get_multi(random_sample_keys)
            # Create the corresponding vote options for that interval (or none interval)
            VoteOptions(vote_type=self.key,
                        show=show,
                        interval=interval,
                        option_list=random_sample_keys).put()
        else:
            # Convert the option list keys into actual entities
            unused_suggestions = ndb.get_multi(interval_vote_options.option_list)
        return unused_suggestions
    
    def get_live_vote_count(show, player=None, suggestion=None, interval=None):
        return LiveVote.query(LiveVote.show == show,
                              LiveVote.vote_type == self.key,
                              LiveVote.player == player,
                              LiveVote.suggestion == suggestion,
                              LiveVote.interval == interval).count()


class Show(ndb.Model):
    # Assigned to show on creation
    vote_length = ndb.IntegerProperty(default=25, indexed=False)
    result_length = ndb.IntegerProperty(default=10, indexed=False)
    vote_options = ndb.IntegerProperty(default=5, indexed=False)
    timezone = ndb.StringProperty(default='America/Denver', indexed=False)

    theme = ndb.KeyProperty(kind=Suggestion, indexed=False)
    vote_types = ndb.KeyProperty(kind=VoteType, repeated=True, indexed=False)
    # All players in the show
    players = ndb.KeyProperty(kind=Player, repeated=True, indexed=False)
    # Finite amount of players to select from during the show
    player_pool = ndb.KeyProperty(kind=Player, repeated=True, indexed=False)
    created = ndb.DateTimeProperty(required=True)
    
    # Changes during live show
    current_vote_type = ndb.KeyProperty(kind=VoteType, indexed=False)
    current_vote_init = ndb.DateTimeProperty(indexed=False)
    recap_type = ndb.KeyProperty(kind=VoteType, indexed=False)
    recap_init = ndb.DateTimeProperty(indexed=False)
    locked = ndb.BooleanProperty(default=False, indexed=False)
    showing_leaderboard = ndb.BooleanProperty(default=False, indexed=False)
    voted_items = ndb.KeyProperty(kind=VotedItem, repeated=True, indexed=False)
    
    def get_player_by_interval(self, interval, vote_type):
        return ShowInterval.query(ShowInterval.show == self.key,
                                  ShowInterval.interval == interval,
                                  ShowInterval.vote_type == vote_type).get()

    @property
    def is_today(self):
        return self.created.date() == get_mountain_time().date()    
    
    @property
    def current_vote_state(self):
        state_dict = {'state': 'default', 'display': 'default', 'used_types': []}
        vote_type = self.current_vote_type.get()
        now = get_mountain_time()
        # Get timezone for comparisons
        now_tz = back_to_tz(now)
        # If any vote has started
        if self.current_vote_init:
            # Get the timezone datetime of the start of the vote type
            init_time_tz = back_to_tz(self.current_vote_init)
            # Get the end of the voting period for the type
            vote_end = init_time_tz + datetime.timedelta(seconds=self.vote_length)
            # Get the end of the overall display of the type
            display_end = vote_end + datetime.timedelta(seconds=self.result_length)
            # If we're in the voting period of this type (and it wasn't voted pre-show)
            if now_tz >= init_time_tz and now_tz <= vote_end and not vote_type.preshow_voted:
                state_dict.update(
                       {'state': vote_type.name,
                        'display': 'voting',
                        # Set the end of the voting period
                        'hour': vote_end.hour,
                        'minute': vote_end.minute,
                        'second': vote_end.second,
                        'voting_length': (vote_end - now_tz).seconds})
            # If we're in the result period of this type (or it was voted pre-show)
            elif now_tz >= vote_end and now_tz <= display_end or vote_type.preshow_voted:
                state_dict.update({'state': vote_type.name,
                                   'display': 'result',
                                   'hour': vote_end.hour,
                                   'minute': vote_end.minute,
                                   'second': vote_end.second})
        # If any recap exists
        if self.recap_init:
            recap_type_entity = self.recap_type.get()
            recap_start_tz = back_to_tz(self.recap_init)
            # Get the end of the recap display
            display_end = recap_start_tz + datetime.timedelta(seconds=self.result_length)
            # If we're in the display period of this recap type
            if now_tz >= recap_start_tz and now_tz <= display_end:
                state_dict.update({'state': recap_type_entity.name,
                                   'display': 'result',
                                   'hour': display_end.hour,
                                   'minute': display_end.minute,
                                   'second': display_end.second})
        
        # Get the list of already voted items
        for vt in self.voted_items:
            voted_item_entity = vt.get()
            vote_type = voted_item_entity.vote_type.get()
            # If the vote type has been used (and is not an interval)
            if not vote_type.has_intervals:
                state_dict['used_types'].append(vote_type.name)
                    
        return state_dict

    def current_vote_options(self, voting_only=False):
        vote_type = self.current_vote_type.get()
        current_interval = vote_type.current_interval
        vote_options = self.current_vote_state.copy()
        state = vote_options.get('state', 'default')
        display = vote_options.get('display')
        if display == 'voting':
            vote_options['options'] = []
            if vote_type.style == 'all-players':
                # Loop through all the players in the show
                for player in self.players:
                    count = vote_type.get_live_vote_count(self.key,
                                                          player=player,
                                                          interval=current_interval)
                    player_dict = {'photo_filename': player.photo_filename,
                                   'id': player.key.id(),
                                   'count': count}
                    vote_options['options'].append(player_dict)
            elif vote_type.style == 'player-pool':
                # Loop through all the players in the show's player pool
                for player in self.player_pool:
                    count = vote_type.get_live_vote_count(self.key,
                                                          player=player,
                                                          interval=current_interval)
                    player_dict = {'photo_filename': player.photo_filename,
                                   'id': player.key.id(),
                                   'count': count}
                    vote_options['options'].append(player_dict)
            elif vote_type.style == 'player-options':
                # Get the current player
                current_player = self.get_player_by_interval(interval, self.current_vote_type)
                vote_options.update({'interval': current_interval,
                                     'player_photo': current_player.get().photo_filename})
                unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                 interval=current_interval)
                for unused_suggestion in unused_suggestions:
                    count = vote_type.get_live_vote_count(self.key,
                                                          suggestion=unused_suggestion,
                                                          interval=current_interval)
                    vote_options['options'].append({'name': unused_suggestion.value,
                                                    'id': unused_suggestion.key.id(),
                                                    'count': count})
            elif vote_type.style == 'options':
                unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                 interval=current_interval)
                for unused_suggestion in unused_suggestions:
                    count = vote_type.get_live_vote_count(self.key,
                                                          suggestion=unused_suggestion,
                                                          interval=current_interval)
                    vote_options['options'].append({'name': unused_suggestion.value,
                                                    'id': unused_suggestion.key.id(),
                                                    'count': count})
            # If there is a 1 minute interval gap between this interval and the next
            if vote_type.get_interval_gap(current_interval) == 1:
                vote_options['speedup'] = True
        elif display == 'result' and not voting_only:
            if vote_type.style == 'all-players':
                # The winning player hasn't been selected
                if not vote_type.current_voted_item:
                    winning_count = 0
                    winning_player = None
                    # Loop through all the players in the show
                    for player in self.players:
                        # Get their live vote count
                        count = vote_type.get_live_vote_count(self.key,
                                                              player=player,
                                                              interval=current_interval)
                        # Compare which player has the highest votes
                        if count >= winning_count:
                            # Set the new winning player/count
                            winning_player = player
                            winning_count = count
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              player=winning_player,
                                              interval=current_interval).put()
                    # Append it to the list of voted items for the show
                    show.voted_items.append(current_voted)
                    show.put()
                # The winning player has already been selected
                else:
                    current_voted = vote_type.current_voted_item.get()
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                          player=vote_type.current_voted_item,
                                                          interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['display_name'] = vote_type.display_name
                vote_options['photo_filename'] = current_voted.player.get().photo_filename
                vote_options['count'] = winning_count
            elif vote_type.style == 'player-pool':
                # The winning player hasn't been selected
                if not vote_type.current_voted_item:
                    winning_count = 0
                    winning_player = None
                    # Loop through all the players left in the show's player pool
                    for player in self.player_pool:
                        # Get their live vote count
                        count = vote_type.get_live_vote_count(self.key,
                                                              player=player,
                                                              interval=current_interval)
                        # Compare which player has the highest votes
                        if count >= winning_count:
                            # Set the new winning player/count
                            winning_player = player
                            winning_count = count
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              player=winning_player,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted)
                    # Pop the player out of the show's player pool
                    for player in list(self.player_pool):
                        if player == winning_player:
                            # Remove the winning player
                            self.player_pool.remove(player)
                    show.put()
                # The winning player has already been selected
                else:
                    current_voted = vote_type.current_voted_item.get()
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  player=vote_type.current_voted_item,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['display_name'] = vote_type.display_name
                vote_options['photo_filename'] = current_voted.player.get().photo_filename
                vote_options['count'] = winning_count
            elif vote_type.style == 'player-options':
                # Get the current player
                current_player = self.get_player_by_interval(interval, self.current_vote_type)
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item:
                    unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                     interval=current_interval)
                    winning_count = 0
                    winning_suggestion = None
                    for unused_suggestion in unused_suggestions:
                        count = vote_type.get_live_vote_count(self.key,
                                                              suggestion=unused_suggestion,
                                                              interval=current_interval)
                        # Compare which suggestion has the highest votes
                        if count >= winning_count:
                            # Set the new winning suggestion/count
                            winning_suggestion = unused_suggestion
                            winning_count = count
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              player=current_player,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted)
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    # Append it to the list of voted items for the show
                    show.voted_items.append(current_voted)
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item.get()
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['photo_filename'] = current_player.photo_filename
                vote_options['suggestion'] = current_voted.suggestion
                vote_options['count'] = winning_count
            elif vote_type.style == 'options':
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item:
                    unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                     interval=current_interval)
                    winning_count = 0
                    winning_suggestion = None
                    for unused_suggestion in unused_suggestions:
                        count = vote_type.get_live_vote_count(self.key,
                                                              suggestion=unused_suggestion,
                                                              interval=current_interval)
                        # Compare which suggestion has the highest votes
                        if count >= winning_count:
                            # Set the new winning suggestion/count
                            winning_suggestion = unused_suggestion
                            winning_count = count
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted)
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    # Append it to the list of voted items for the show
                    show.voted_items.append(current_voted)
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item.get()
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['suggestion'] = current_voted.suggestion
                vote_options['count'] = winning_count
            elif vote_type.style == 'preshow-voted':
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item:
                    unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                     interval=current_interval)
                    winning_suggestion = unused_suggestions[0]
                    # Get the winning pre-show vote value
                    winning_count = winning_suggestion.suggestion.get().preshow_value
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted)
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    # Append it to the list of voted items for the show
                    show.voted_items.append(current_voted)
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item.get()
                    # Get the winning pre-show vote value
                    winning_count = current_voted.suggestion.get().preshow_value
                vote_options['voted'] = vote_type.name
                vote_options['suggestion'] = current_voted.suggestion
                vote_options['count'] = winning_count
        
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
    vote_type = ndb.KeyProperty(kind=VoteType, required=True)
    player = ndb.KeyProperty(kind=Player, required=True)
    interval = ndb.IntegerProperty(required=True)


class VoteOptions(ndb.Model):
    show = ndb.KeyProperty(kind=Show, required=True)
    vote_type = ndb.KeyProperty(kind=VoteType, required=True)
    interval = ndb.IntegerProperty()
    option_list = ndb.KeyProperty(kind=Suggestion, repeated=True)


class VotedItem(ndb.Model):
    vote_type = ndb.KeyProperty(kind=VoteType, required=True)
    suggestion = ndb.KeyProperty(kind=Suggestion)
    player = ndb.KeyProperty(kind=Player)
    interval = ndb.IntegerProperty()
