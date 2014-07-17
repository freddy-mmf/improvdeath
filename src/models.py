import datetime
import math
import random

from google.appengine.ext import ndb

from timezone import (get_mountain_time, back_to_tz, get_today_start,
                      get_tomorrow_start)

VOTE_STYLE = ['player-options', 'player-pool', 'options',
              'preshow-voted', 'all-players', 'test']
OCCURS_TYPE = ['during', 'before']


def get_current_show():
    return Show.query(
            Show.created >= get_today_start(),
            Show.created < get_tomorrow_start()).order(-Show.created).get()


class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    photo_filename = ndb.StringProperty(required=True, indexed=False)
    date_added = ndb.DateTimeProperty()
    
    @property
    def img_path(self):
        return "/static/img/players/%s" % self.photo_filename


class SuggestionPool(ndb.Model):
    name = ndb.StringProperty(required=True)
    display_name = ndb.StringProperty(required=True, indexed=False)
    description = ndb.TextProperty(required=True, indexed=False)
    
    created = ndb.DateProperty(required=True)
    
    @property
    def available_suggestions(self):
        return Suggestion.query(Suggestion.suggestion_pool == self.key,
                                Suggestion.used == False).count()
    
    @property
    def delete_all_suggestions_and_live_votes(self):
        # Get all the pools suggestions
        suggestions = Suggestion.query(Suggestion.suggestion_pool == self.key,
                                       ).fetch(keys_only=True)
        # Get all the live votes for that suggestion
        for suggestion in suggestions:
            live_votes = LiveVote.query(LiveVote.suggestion == suggestion,
                                        ).fetch(keys_only=True)
            # Delete the live votes
            ndb.delete_multi(live_votes)
        # Delete all the pool suggestions
        ndb.delete_multi(suggestions)
    
    def put(self, *args, **kwargs):
        if not self.created:
            self.created = get_mountain_time()
        return super(SuggestionPool, self).put(*args, **kwargs)


class VoteType(ndb.Model):
    name = ndb.StringProperty(required=True)
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
    button_color = ndb.StringProperty(default="#003D7A", indexed=False)

    @property
    def get_next_interval(self):
        # If given an interval
        if self.current_interval != None:
            # Loop through the intervals in order
            for i in range(0, len(self.intervals)):
                if self.current_interval == self.intervals[i]:
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
        next_interval = self.get_next_interval
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
    
    def current_voted_item(self, show):
        return VotedItem.query(VotedItem.vote_type == self.key,
                               VotedItem.vote_type == show,
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
            # Mark the suggestions as voted on
            for unused_suggestion in unused_suggestions:
                unused_suggestion.voted_on = True
                unused_suggestion.put()
            # Create the corresponding vote options for that interval (or none interval)
            VoteOptions(vote_type=self.key,
                        show=show,
                        interval=interval,
                        option_list=random_sample_keys).put()
        else:
            # Convert the option list keys into actual entities
            unused_suggestions = ndb.get_multi(interval_vote_options.option_list)
        return unused_suggestions
    
    def get_live_vote_count(self, show, player=None, suggestion=None, interval=None):
        return LiveVote.query(LiveVote.show == show,
                              LiveVote.vote_type == self.key,
                              LiveVote.player == player,
                              LiveVote.suggestion == suggestion,
                              LiveVote.interval == interval).count()
    
    def get_test_options(self, show):
        # Get the stored interval options
        vote_options = VoteOptions.query(VoteOptions.vote_type == self.key,
                                         VoteOptions.show == show).get()
        if not vote_options:
            self.suggestion_pool.get().delete_all_suggestions_and_live_votes
            test_options = ["I'm JAZZED! Start the show already!",
                            "I'm definitely excited.",
                            "I didn't actually read anything. I just pressed a button.",
                            "This seems... interesting...",
                            "If you see me sleeping in the audience, try to keep it down."]
            vote_option_list = []
            for i in range(0, self.options):
                suggestion = Suggestion(show=show,
                                        suggestion_pool=self.suggestion_pool,
                                        value=test_options[i],
                                        session_id='fake').put()
                vote_option_list.append(suggestion)
            # Create the corresponding vote options for that interval (or none interval)
            VoteOptions(vote_type=self.key,
                        show=show,
                        option_list=vote_option_list).put()
        else:
            vote_option_list = vote_options.option_list
        # Convert the option list keys into actual entities
        suggestions = ndb.get_multi(vote_option_list)
        return suggestions
                


class Show(ndb.Model):
    # Assigned to show on creation
    vote_length = ndb.IntegerProperty(default=25, indexed=False)
    result_length = ndb.IntegerProperty(default=10, indexed=False)
    vote_options = ndb.IntegerProperty(default=5, indexed=False)
    timezone = ndb.StringProperty(default='America/Denver', indexed=False)
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
    voted_items = ndb.IntegerProperty(repeated=True, indexed=False)
    
    @property
    def show_option_list(self):
        return range(1, self.vote_options+1)
    
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
        # If any vote has started, get the vote type
        if self.current_vote_type:
            vote_type = self.current_vote_type.get()
        # Just return the default state
        else:
            return state_dict
        now = get_mountain_time()
        # Get timezone for comparisons
        now_tz = back_to_tz(now)
        # If any vote has started, see if it's currently running
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
                        'style': vote_type.style,
                        # Set the end of the voting period
                        'hour': vote_end.hour,
                        'minute': vote_end.minute,
                        'second': vote_end.second,
                        'voting_length': (vote_end - now_tz).seconds})
            # If we're in the result period of this type (or it was voted pre-show)
            elif now_tz >= vote_end and now_tz <= display_end or vote_type.preshow_voted:
                state_dict.update({'state': vote_type.name,
                                   'display': 'result',
                                   'style': vote_type.style,
                                   'display_name': vote_type.display_name,
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
                                   'style': vote_type.style,
                                   'display_name': vote_type.display_name,
                                   'hour': display_end.hour,
                                   'minute': display_end.minute,
                                   'second': display_end.second})
        
        # Get the list of already voted items
        for vi_id in self.voted_items:
            voted_item_entity = ndb.Key(VotedItem, int(vi_id)).get()
            vote_type = voted_item_entity.vote_type.get()
            # If the vote type has been used (and is not an interval)
            if not vote_type.has_intervals:
                state_dict['used_types'].append(vote_type.name)
                    
        return state_dict

    def current_vote_options(self, voting_only=False):
        vote_options = self.current_vote_state.copy()
        # If any vote has started, get the vote type and figure out what state we're in
        if self.current_vote_type:
            vote_type = self.current_vote_type.get()
        # Just return the default state
        else:
            return vote_options
        current_interval = vote_type.current_interval
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
                current_player = self.get_player_by_interval(interval, vote_type.key)
                vote_options.update({'interval': current_interval,
                                     'player_photo': current_player.get().photo_filename})
                unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                 interval=current_interval)
                for unused_suggestion in unused_suggestions:
                    count = vote_type.get_live_vote_count(self.key,
                                                          suggestion=unused_suggestion,
                                                          interval=current_interval)
                    vote_options['options'].append({'value': unused_suggestion.value,
                                                    'id': unused_suggestion.key.id(),
                                                    'count': count})
            elif vote_type.style == 'options':
                unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                 interval=current_interval)
                for unused_suggestion in unused_suggestions:
                    count = vote_type.get_live_vote_count(self.key,
                                                          suggestion=unused_suggestion,
                                                          interval=current_interval)
                    vote_options['options'].append({'value': unused_suggestion.value,
                                                    'id': unused_suggestion.key.id(),
                                                    'count': count})
            elif vote_type.style == 'test':
                suggestions = vote_type.get_test_options(self.key)
                for suggestion in suggestions:
                    count = vote_type.get_live_vote_count(self.key,
                                                          suggestion=suggestion.key)
                    vote_options['options'].append({'value': suggestion.value,
                                                    'id': suggestion.key.id(),
                                                    'count': count})
            # If there is a 1 minute interval gap between this interval and the next
            if vote_type.get_interval_gap(current_interval) == 1:
                vote_options['speedup'] = True
        elif display == 'result' and not voting_only:
            if vote_type.style == 'all-players':
                # The winning player hasn't been selected
                if not vote_type.current_voted_item(self.key):
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
                                              show=self.key,
                                              player=winning_player,
                                              interval=current_interval).put()
                    # Append it to the list of voted items for the show
                    show.voted_items.append(current_voted.key.id())
                    show.put()
                # The winning player has already been selected
                else:
                    current_voted = vote_type.current_voted_item(self.key)
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  player=current_voted.player,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['photo_filename'] = current_voted.player.get().photo_filename
                vote_options['count'] = winning_count
            elif vote_type.style == 'player-pool':
                # The winning player hasn't been selected
                if not vote_type.current_voted_item(self.key):
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
                                              show=self.key,
                                              player=winning_player,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted.key.id())
                    # Pop the player out of the show's player pool
                    for player in list(self.player_pool):
                        if player == winning_player:
                            # Remove the winning player
                            self.player_pool.remove(player)
                    show.put()
                # The winning player has already been selected
                else:
                    current_voted = vote_type.current_voted_item(self.key)
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  player=current_voted.player,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['photo_filename'] = current_voted.player.get().photo_filename
                vote_options['count'] = winning_count
            elif vote_type.style == 'player-options':
                # Get the current player
                current_player = self.get_player_by_interval(interval, vote_type.key)
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item(self.key):
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
                                              show=self.key,
                                              player=current_player,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted.key.id())
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item(self.key)
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  suggestion=current_voted.suggestion,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['photo_filename'] = current_player.photo_filename
                vote_options['value'] = current_voted.suggestion.get().value
                vote_options['count'] = winning_count
            elif vote_type.style == 'options':
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item(self.key):
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
                                              show=self.key,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted.key.id())
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item(self.key)
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  suggestion=current_voted.suggestion,
                                                                  interval=current_interval)
                vote_options['voted'] = vote_type.name
                vote_options['value'] = current_voted.suggestion.get().value
                vote_options['count'] = winning_count
            elif vote_type.style == 'test':
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item(self.key):
                    suggestions = vote_type.get_test_options(self.key)
                    winning_count = 0
                    winning_suggestion = None
                    for suggestion in suggestions:
                        count = vote_type.get_live_vote_count(self.key,
                                                              suggestion=suggestion)
                        # Compare which suggestion has the highest votes
                        if count >= winning_count:
                            # Set the new winning suggestion/count
                            winning_suggestion = suggestion
                            winning_count = count
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              show=self.key,
                                              suggestion=winning_suggestion).put()
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    show.put()
                # The winning suggestion has already been selected
                else:
                    # Get the stored interval options
                    vote_options = VoteOptions.query(VoteOptions.vote_type == self.key,
                                                     VoteOptions.show == show).delete()
                    current_voted = vote_type.current_voted_item(self.key)
                    winning_count = vote_type.get_live_vote_count(self.key,
                                                                  suggestion=current_voted.suggestion)
                vote_options['voted'] = vote_type.name
                vote_options['value'] = current_voted.suggestion.get().value
                vote_options['count'] = winning_count
            elif vote_type.style == 'preshow-voted':
                # The winning suggestion hasn't been selected
                if not vote_type.current_voted_item(self.key):
                    unused_suggestions = vote_type.get_randomized_unused_suggestions(self.key,
                                                                                     interval=current_interval)
                    winning_suggestion = unused_suggestions[0]
                    # Get the winning pre-show vote value
                    winning_count = winning_suggestion.suggestion.get().preshow_value
                    # Create the current voted
                    current_voted = VotedItem(vote_type=vote_type.key,
                                              show=self.key,
                                              suggestion=winning_suggestion,
                                              interval=current_interval).put()
                    # Append it to the list of current voted items for the show
                    show.voted_items.append(current_voted.key.id())
                    # Mark the suggestion as used
                    winning_suggestion.used = True
                    winning_suggestion.put()
                    show.put()
                # The winning suggestion has already been selected
                else:
                    current_voted = vote_type.current_voted_item(self.key)
                    # Get the winning pre-show vote value
                    winning_count = current_voted.suggestion.get().preshow_value
                vote_options['voted'] = vote_type.name
                vote_options['value'] = current_voted.suggestion.get().value
                vote_options['count'] = winning_count
        
        return vote_options
    
    def put(self, *args, **kwargs):
        # If created wasn't specified yet
        if not self.created:
            self.created = get_mountain_time()
        return super(Show, self).put(*args, **kwargs)


class Suggestion(ndb.Model):
    show = ndb.KeyProperty(kind=Show)
    suggestion_pool = ndb.KeyProperty(kind=SuggestionPool, required=True)
    used = ndb.BooleanProperty(default=False)
    voted_on = ndb.BooleanProperty(default=False)
    value = ndb.StringProperty(required=True, indexed=False)
    # Pre-show upvotes
    preshow_value = ndb.IntegerProperty(default=0)
    session_id = ndb.StringProperty(required=True)
    user = ndb.UserProperty(default=None)
    
    created = ndb.DateTimeProperty()
    
    def get_live_vote_exists(self, show, interval, session_id):
        """Determine if a live vote exists for this suggestion by this session"""
        return bool(LiveVote.query(
                    LiveVote.suggestion == self.key,
                    LiveVote.show == show,
                    LiveVote.interval == interval,
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
            suggestion_entity.voted_on = True
            suggestion_entity.put()
        return super(LiveVote, self).put(*args, **kwargs)


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
    show = ndb.KeyProperty(kind=Show, required=True)
    suggestion = ndb.KeyProperty(kind=Suggestion)
    player = ndb.KeyProperty(kind=Player)
    interval = ndb.IntegerProperty(default=None)
