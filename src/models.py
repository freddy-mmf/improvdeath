import datetime
import random

from google.appengine.ext import ndb

from timezone import get_mountain_time, back_to_tz

VOTE_AFTER_INTERVAL = 8
DISPLAY_VOTED = 8
WILDCARD_AMOUNT = 5
ITEM_AMOUNT = 5
ROLE_TYPES = ['hero', 'villain', 'shapeshifter', 'lover']
VOTE_TYPES = list(ROLE_TYPES)
VOTE_TYPES += ['item', 'wildcard', 'incident', 'test']
VOTE_OPTIONS = 5
ACTION_OPTIONS = 3
INCIDENT_AMOUNT = 5


def get_vote_percentage(subset_count, all_count):
    # If either of the two counts are zero, return zero percent
    if subset_count == 0 or all_count == 0:
        return 0
    return int(math.floor(100 * float(subset_count)/float(all_count)))


class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    photo_filename = ndb.StringProperty(required=True)
    date_added = ndb.DateTimeProperty()
    
    @property
    def img_path(self):
        return "/static/img/players/%s" % self.photo_filename
    
    @property
    def get_live_action_vote(self, show, interval, session_id):
        return LiveActionVote.query(
                    LiveActionVote.player == self.key,
                    LiveActionVote.interval == int(interval),
                    LiveActionVote.show == show,
                    LiveActionVote.session_id == str(session_id)).get()

    def get_all_live_action_count(self, interval):
        return LiveActionVote.query(
                        LiveActionVote.player == self.key,
                        LiveActionVote.interval == int(interval),
                        LiveActionVote.created == get_mountain_time().date()).count()

    def get_live_action_percentage(self, action, interval, all_votes):
        action_votes = LiveActionVote.query(
                        LiveActionVote.action == action,
                        LiveActionVote.player == self.key,
                        LiveActionVote.interval == int(interval),
                        LiveActionVote.created == get_mountain_time().date()).count()
        return get_vote_percentage(action_votes, all_votes)
    
    @property
    def get_role_vote(self, show, role):
        return RoleVote.query(
                    RoleVote.player == self.key,
                    RoleVote.show == show,
                    RoleVote.role == role).get()


class Action(ndb.Model):
    description = ndb.StringProperty(required=True)
    created = ndb.DateProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    live_vote_value = ndb.IntegerProperty(default=0)
    
    @property
    def get_live_action_vote(self, session_id):
        return LiveActionVote.query(
                    LiveActionVote.action == self.key,
                    LiveActionVote.session_id == str(session_id)).get()
    
    def live_vote_percent(self, show):
        all_count = LiveActionVote.query(LiveActionVote.show == show,
                                         LiveActionVote.interval == -1).count()
        return get_vote_percentage(self.live_vote_value, all_count)

    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(Action, self).put(*args, **kwargs)


class Theme(ndb.Model):
    created = ndb.DateTimeProperty(required=True)
    name = ndb.StringProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    
    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(Theme, self).put(*args, **kwargs)


class VotingTest(ndb.Model):
    name = ndb.StringProperty(required=True)
    live_vote_value = ndb.IntegerProperty(default=0)
    
    @property
    def get_live_test_vote(self, session_id):
        return LiveVotingTest.query(
                    LiveVotingTest.item == self.key,
                    LiveVotingTest.session_id == str(session_id)).get()
    
    def live_vote_percent(self, show):
        all_count = LiveVotingTest.query(LiveVotingTest.show == show).count()
        return get_vote_percentage(self.live_vote_value, all_count)


class Item(ndb.Model):
    created = ndb.DateTimeProperty(required=True)
    name = ndb.StringProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    live_vote_value = ndb.IntegerProperty(default=0)
    
    @property
    def get_live_item_vote(self, session_id):
        return LiveItemVote.query(
                    LiveItemVote.item == self.key,
                    LiveItemVote.session_id == str(session_id)).get()
    
    def live_vote_percent(self, show):
        all_count = LiveItemVote.query(LiveItemVote.show == show).count()
        return get_vote_percentage(self.live_vote_value, all_count)
    
    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(Item, self).put(*args, **kwargs)


class WildcardCharacter(ndb.Model):
    created = ndb.DateTimeProperty(required=True)
    name = ndb.StringProperty(required=True)
    used = ndb.BooleanProperty(default=False)
    vote_value = ndb.IntegerProperty(default=0)
    live_vote_value = ndb.IntegerProperty(default=0)
    
    @property
    def get_live_wc_vote(self, session_id):
        return LiveWildcardCharacterVote.query(
                    LiveWildcardCharacterVote.wildcard == self.key,
                    LiveWildcardCharacterVote.session_id == str(session_id)).get()
    
    def live_vote_percent(self, show):
        all_count = LiveWildcardCharacterVote.query(
            LiveWildcardCharacterVote.show == show).count()
        return get_vote_percentage(self.live_vote_value, all_count)
    
    def put(self, *args, **kwargs):
        self.created = get_mountain_time()
        return super(WildcardCharacter, self).put(*args, **kwargs)


class Show(ndb.Model):
    scheduled = ndb.DateTimeProperty()
    theme = ndb.KeyProperty(kind=Theme)
    length = ndb.IntegerProperty(required=True)
    start_time = ndb.DateTimeProperty()
    end_time = ndb.DateTimeProperty()
    test_vote_init = ndb.DateTimeProperty()
    item_vote_init = ndb.DateTimeProperty()
    hero_vote_init = ndb.DateTimeProperty()
    villain_vote_init = ndb.DateTimeProperty()
    incident_vote_init = ndb.DateTimeProperty()
    wildcard_vote_init = ndb.DateTimeProperty()
    shapeshifter_vote_init = ndb.DateTimeProperty()
    lover_vote_init = ndb.DateTimeProperty()
    incident = ndb.KeyProperty(kind=Action)
    test = ndb.KeyProperty(kind=VotingTest)
    item = ndb.KeyProperty(kind=Item)
    hero = ndb.KeyProperty(kind=Player)
    villain = ndb.KeyProperty(kind=Player)
    wildcard = ndb.KeyProperty(kind=WildcardCharacter)
    shapeshifter = ndb.KeyProperty(kind=Player)
    lover = ndb.KeyProperty(kind=Player)
    
    @property
    def start_time_tz(self):
        return back_to_tz(self.start_time)
    
    @property
    def end_time_tz(self):
        return back_to_tz(self.end_time)
    
    @property
    def scheduled_tz(self):
        return back_to_tz(self.scheduled)
    
    def get_player_action_by_interval(self, interval):
        for pa in self.player_actions:
            if pa.interval == int(interval):
                return pa
        raise ValueError(
            "Player action for this interval doesn't exists, interval: %s" % interval)
    
    def get_player_by_interval(self, interval):
        pa = self.get_player_action_by_interval(interval)
        return pa.player
        
    @property
    def players(self):
        show_players = ShowPlayer.query(ShowPlayer.show == self.key).fetch()
        return [x.player.get() for x in show_players if getattr(x, 'player', None)]
    
    @property
    def player_actions(self):
        action_intervals = ShowAction.query(ShowAction.show == self.key).fetch()
        return [x.player_action.get() for x in action_intervals if getattr(x, 'player_action', None) and x.player_action.get()]
    
    @property
    def running(self):
        #return True
        if not self.start_time or not self.end_time:
            return False
        now_tz = back_to_tz(get_mountain_time())
        if now_tz >= self.start_time_tz and now_tz <= self.end_time_tz:
            return True
        return False
    
    @property
    def current_interval(self):
        # If the interval show has started
        if self.start_time:
            # Determine how many minutes have elapsed in the show
            now_tz = back_to_tz(get_mountain_time())
            delta = now_tz - self.start_time_tz
            minutes_elapsed = (delta.seconds//60)%60
            max_interval = 0
            # Look through the player actions
            for pa in self.player_actions:
                # If we're at or past the minutes elapsed
                # And this is the furthest along interval we've found
                if minutes_elapsed >= pa.interval and pa.interval > max_interval:
                    # Set it to the furthest interval we've reached
                    max_interval = interval
            # Return the furthest interval we've reached
            return max_interval
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
                           {'state': vote_type, 'display': 'voting',
                            # Set the end of the voting period
                            'hour': vote_end.hour,
                            'minute': vote_end.minute,
                            'second': vote_end.second})
                elif now_tz >= vote_end and now_tz <= display_end:
                    state_dict.update({'state': vote_type, 'display': 'result'})
        
        # Get the list of used vote types
        for vt in VOTE_TYPES:
            # If the vote type has been used
            if getattr(self, vt, None):
                state_dict['used_types'].append(vt)
                    
        return state_dict

    def current_vote_options(self, show):
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
                    percent = vt.live_vote_percent(show.key)
                    vote_options['options'].append({'name': vt.name,
                                                    'id': vt.key.id(),
                                                    'percent': percent})
            # If we are showing the results of the vote
            elif display == 'result':
                # Set the most voted test if it isn't already set
                if not show.test:
                    voted_test = VotingTest.query().order(
                                             -VotingTest.live_vote_value).get()
                    show.test = voted_test.key
                    show.put()
                    voted_test.put()
                vote_options['voted'] = show.test.get().name
                vote_options['count'] = show.test.get().live_vote_value
                vote_options['percent'] = show.test.get().live_vote_percent(show.key)
        # If an item has been triggered
        elif state == 'item':
            # If we're in the voting phase for an item
            if display == 'voting':
                items = Item.query(Item.used == False,
                           ).order(-Item.vote_value,
                                   Item.created).fetch(ITEM_AMOUNT)
                vote_options['options'] = []
                for item in items:
                    percent = item.live_vote_percent(show.key)
                    vote_options['options'].append({'name': item.name,
                                                    'id': item.key.id(),
                                                    'percent': percent})
            # If we are showing the results of the vote
            elif display == 'result':
                # Set the most voted item if it isn't already set
                if not show.item:
                    voted_item = Item.query(Item.used == False,
                                     ).order(-Item.live_vote_value,
                                             -Item.vote_value,
                                             Item.created).get()
                    show.item = voted_item.key
                    show.put()
                    # Set the item as used
                    voted_item.used = True
                    voted_item.put()
                vote_options['voted'] = show.item.get().name
                vote_options['count'] = show.item.get().live_vote_value
                vote_options['percent'] = show.item.get().live_vote_percent(show.key)
        # If an wildcard character has been triggered
        elif state == 'wildcard':
            # If we're in the voting phase for a wildcard character
            if display == 'voting':
                wcs = WildcardCharacter.query(WildcardCharacter.used == False,
                          ).order(-WildcardCharacter.vote_value,
                                  WildcardCharacter.created).fetch(WILDCARD_AMOUNT)
                vote_options['options'] = []
                for wc in wcs:
                    percent = wc.live_vote_percent(show.key)
                    vote_options['options'].append({'name': wc.name,
                                                    'id': wc.key.id(),
                                                    'percent': percent})
            # If we are showing the results of the vote
            elif display == 'result':
                # Set the most voted wildcard character if it isn't already set
                if not show.wildcard:
                    voted_wc = WildcardCharacter.query(WildcardCharacter.used == False,
                                   ).order(-WildcardCharacter.live_vote_value,
                                           -WildcardCharacter.vote_value,
                                           WildcardCharacter.created).get()
                    show.wildcard = voted_wc.key
                    show.put()
                    # Set the wildcard character as used
                    voted_wc.used = True
                    voted_wc.put()
                percent = show.wildcard.get().live_vote_percent(show.key)
                vote_options['voted'] = show.wildcard.get().name
                vote_options['count'] = show.wildcard.get().live_vote_value
                vote_options['percent'] = percent
        # If an incident has been triggered
        elif state == 'incident':
            # If we're in the voting phase for an incident
            if display == 'voting':
                actions = Action.query(Action.used == False,
                          ).order(-Action.vote_value,
                                  Action.created).fetch(INCIDENT_AMOUNT)
                vote_options['options'] = []
                for action in actions:
                    percent = action.live_vote_percent(show.key)
                    vote_options['options'].append({'name': action.description,
                                                    'id': action.key.id(),
                                                    'percent': percent})
            # If we are showing the results of the vote
            elif display == 'result':
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
                percent = show.incident.get().live_vote_percent(show.key)
                vote_options['voted'] = show.incident.get().description
                vote_options['count'] = show.incident.get().live_vote_value
                vote_options['percent'] = percent
        # If a role vote has been triggered
        elif state in ROLE_TYPES:
            vote_options['role'] = True
            # If we're in the voting phase for the role
            if display == 'voting':
                vote_options['options'] = []
                # Loop through all the players in the show
                for player in show.players:
                    # Make sure the user isn't already the hero
                    if player.key != show.hero:
                        # Get the live voting percentage for a role
                        change_vote = get_or_create_role_vote(show, player, state)
                        player_dict = {'photo_filename': player.photo_filename,
                                       'id': player.key.id(),
                                       'percent': change_vote.live_role_vote_percent}
                        vote_options['options'].append(player_dict)
            # If we are showing the results of the vote
            elif display == 'result':
                role_player = getattr(show, state, None)
                # Set the role if it isn't already set
                if not role_player:
                    voted_role = RoleVote.query(RoleVote.role == state,
                                                RoleVote.show == show.key,
                                                RoleVote.player != show.hero,
                                     ).order(RoleVote.player,
                                             -RoleVote.live_vote_value).get()
                    # Setting role for the show
                    setattr(show, state, voted_role.player)
                    show.put()
                    # Getting the player selected for the role
                    role_player = voted_role.player
                else:
                    voted_role = RoleVote.query(RoleVote.role == state,
                                                RoleVote.show == show.key,
                                                RoleVote.player == role_player).get()
                percent = voted_role.live_role_vote_percent
                vote_options['voted'] = state.title()
                vote_options['photo_filename'] = role_player.get().photo_filename
                vote_options['count'] = voted_role.live_vote_value
                vote_options['percent'] = percent
        return vote_options

    def current_action_options(self):
        interval = self.current_interval
        # Get the player
        player = self.get_player_by_interval(interval)
        action_data = {'state': 'interval',
                       'interval': interval,
                       'player_id': player.id(),
                       'player_photo': player.get().photo_filename}
        # Determine if we've already voted on this interval
        now = get_mountain_time()
        # Add timezone for comparisons
        now_tz = back_to_tz(now)
        interval_vote_end = self.start_time_tz + datetime.timedelta(minutes=int(interval)) \
                              + datetime.timedelta(seconds=VOTE_AFTER_INTERVAL)
        if now_tz > interval_vote_end:
            action_data['display'] = 'result'
            player_action = self.get_player_action_by_interval(interval)
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
                                       ).order(-Action.live_vote_value,
                                               Action.created).get()
                # If no live action votes were cast
                # take the highest regular voted action that hasn't been used
                else:
                    # Get the most voted, un-used action
                    voted_action = Action.query(
                                       Action.used == False,
                                       ).order(-Action.vote_value,
                                               Action.created).get()
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
                action_data.update({'voted': voted_action.description,
                                    'count': voted_action.live_vote_value,
                                    'percent': percent})
            else:
                all_votes = player.get().get_all_live_action_count(interval)
                percent = player.get().get_live_action_percentage(player_action.action,
                                                                    interval,
                                                                    all_votes)
                action_data.update({'voted': player_action.action.get().description,
                                    'count': player_action.action.get().live_vote_value,
                                    'percent': percent})
        elif now_tz < interval_vote_end:
            action_data['display'] = 'voting'
            # Return un-used actions, sorted by vote
            unused_actions = Action.query(Action.used == False,
                                 ).order(-Action.vote_value,
                                         Action.created).fetch(ACTION_OPTIONS)
            all_votes = player.get().get_all_live_action_count(interval)
            action_data['options'] = []
            for i in range(0, ACTION_OPTIONS):
                percent = player.get().get_live_action_percentage(unused_actions[i].key,
                                                                    interval,
                                                                    all_votes)
                try:
                    action_data['options'].append({
                                        'name': unused_actions[i].description,
                                        'id': unused_actions[i].key.id(),
                                        'percent': percent})
                except IndexError:
                    pass
        return action_data
    
    def put(self, *args, **kwargs):
        # If start_time is specified, it must mean a show has started
        if self.start_time and self.length:
            # Set the end time of the show
            self.end_time = self.start_time + datetime.timedelta(minutes=self.length)
            # Make a copy of the list of players and randomize it
            rand_players = self.players
            random.shuffle(rand_players, random.random)
            for player_action in self.player_actions:
                # If random players list gets empty, refill it with more players
                if len(rand_players) == 0:
                    rand_players = self.players
                    random.shuffle(rand_players, random.random)
                # Pop a random player off the list
                player_action.player = rand_players.pop().key
                player_action.time_of_action = self.start_time + \
                                      datetime.timedelta(minutes=player_action.interval)
                player_action.put()
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
    time_of_action = ndb.DateTimeProperty()
    action = ndb.KeyProperty(kind=Action)

    @property
    def time_of_action_tz(self):
        return back_to_tz(self.time_of_action)


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


class ItemVote(ndb.Model):
    item = ndb.KeyProperty(kind=Item, required=True)
    session_id = ndb.StringProperty(required=True)
    
    def put(self, *args, **kwargs):
        item = Item.query(Item.key == self.item).get()
        item.vote_value += 1
        item.put()
        return super(ItemVote, self).put(*args, **kwargs)


class LiveItemVote(ndb.Model):
    item = ndb.KeyProperty(kind=Item, required=True)
    show = ndb.KeyProperty(kind=Show, required=True)
    session_id = ndb.StringProperty(required=True)

    def put(self, *args, **kwargs):
        item = Item.query(Item.key == self.item).get()
        item.live_vote_value += 1
        item.put()
        return super(LiveItemVote, self).put(*args, **kwargs)


class WildcardCharacterVote(ndb.Model):
    wildcard = ndb.KeyProperty(kind=WildcardCharacter, required=True)
    session_id = ndb.StringProperty(required=True)
    
    def put(self, *args, **kwargs):
        wildcard = WildcardCharacter.query(
            WildcardCharacter.key == self.wildcard).get()
        wildcard.vote_value += 1
        wildcard.put()
        return super(WildcardCharacterVote, self).put(*args, **kwargs)


class LiveWildcardCharacterVote(ndb.Model):
    wildcard = ndb.KeyProperty(kind=WildcardCharacter, required=True)
    show = ndb.KeyProperty(kind=Show, required=True)
    session_id = ndb.StringProperty(required=True)

    def put(self, *args, **kwargs):
        wildcard = WildcardCharacter.query(
            WildcardCharacter.key == self.wildcard).get()
        wildcard.live_vote_value += 1
        wildcard.put()
        return super(LiveWildcardCharacterVote, self).put(*args, **kwargs)


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

    @property
    def live_role_vote_percent(self):
        all_count = LiveRoleVote.query(
            LiveRoleVote.show == self.show,
            LiveRoleVote.role == self.role).count()
        return get_vote_percentage(self.live_vote_value, all_count)

    @property
    def get_live_role_vote(self, session_id):
        return LiveRoleVote.query(
                    LiveRoleVote.show == self.show,
                    LiveRoleVote.player == self.player,
                    LiveRoleVote.role == self.role,
                    LiveRoleVote.session_id == str(session_id)).get()


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
        role_vote.save()
        return super(LiveRoleVote, self).put(*args, **kwargs)