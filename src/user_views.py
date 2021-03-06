import datetime
import webapp2

from google.appengine.ext.webapp import template
from google.appengine.ext import ndb
from google.appengine.api import taskqueue

from views_base import ViewBase, redirect_locked
from models import (Show, Player, Action, Theme, ActionVote, ThemeVote,
                    LiveActionVote, RoleVote, LiveRoleVote,
                    VotingTest, LiveVotingTest,
                    VOTE_AFTER_INTERVAL, ROLE_TYPES,
                    get_current_show)
from timezone import get_mountain_time, get_tomorrow_start


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
    
    # If an new entity was created
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
    @redirect_locked
    def get(self):
        context = {'current_show': get_current_show()}
        self.response.out.write(template.render(self.path('home.html'),
                                                self.add_context(context)))


class LiveVote(ViewBase):
    def get(self):
        context = {'show': get_current_show()}
        self.response.out.write(template.render(self.path('live_vote.html'),
                                                self.add_context(context)))

    def post(self):
        voted = True
        vote_num = int(self.request.get('vote_num', '0'))
        session_id = str(self.session.get('id'))
        
        # Add the task to the default queue.
        taskqueue.add(url='/live_vote_worker/',
                      params={'show': self.context['current_show'],
                              'vote_num': vote_num,
                              'session_id': session_id})
        context = {'show': self.context['current_show'],
                   'voted': voted}
        self.response.out.write(template.render(self.path('live_vote.html'),
                                                self.add_context(context)))


class LiveVoteWorker(webapp2.RequestHandler):
    def post(self):
        # Get the current show
        show = get_current_show()
        vote_num = int(self.request.get('vote_num'))
        session_id = self.request.get('session_id')
        vote_data = show.current_vote_options(show, voting_only=True)
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
            action = ndb.Key(Action, int(voted_option['id']))
            # If the user hasn't already voted for the incident
            if not action.get().get_live_action_vote_exists(show.key, interval, session_id):
                # If we haven't selected a hero yet
                if not show.hero:
                    # Make sure there is at least SOME player to attach the vote to
                    vote_player = Player.query().get().key
                else:
                    vote_player = show.hero
                LiveActionVote(action=action,
                               show=show.key,
                               player=vote_player,
                               interval=interval,
                               created=get_mountain_time().date(),
                               session_id=session_id).put()
        # Submitting an item vote
        elif state == 'test':
            test = ndb.Key(VotingTest, int(voted_option['id']))
            # If the user hasn't already voted for an item
            if not test.get().get_live_test_vote_exists(show.key, session_id):
                LiveVotingTest(test=test,
                               show=show.key,
                               session_id=session_id).put()


class AddActions(ViewBase):
    
    @redirect_locked
    def get(self):
        actions = Action.query(
            Action.used == False).order(-Action.vote_value,
                                        Action.created).fetch()
        context = {'actions': actions,
                   'show': get_current_show(),
                   'session_id': str(self.session.get('id', '0')),
                   'item_count': len(actions)}
        self.response.out.write(template.render(self.path('add_actions.html'),
                                                self.add_context(context)))

    @redirect_locked
    def post(self):
        context = pre_show_voting_post('action',
                                       'description',
                                       Action,
                                       ActionVote,
                                       self.request,
                                       str(self.session.get('id', '0')),
                                       self.context.get('is_admin', False))
        context['show'] = get_current_show()
        context['item_count'] = len(context.get('actions', 0))
            
        self.response.out.write(template.render(self.path('add_actions.html'),
                                                self.add_context(context)))

        

class AddThemes(ViewBase):
    @redirect_locked
    def get(self):
        themes = Theme.query(
                    Theme.used == False).order(-Theme.vote_value,
                                               Theme.created).fetch()
        context = {'themes': themes,
                   'session_id': str(self.session.get('id', '0')),
                   'item_count': len(themes)}
        self.response.out.write(template.render(self.path('add_themes.html'),
                                                self.add_context(context)))

    @redirect_locked
    def post(self):
        context = pre_show_voting_post('theme',
                                       'name',
                                       Theme,
                                       ThemeVote,
                                       self.request,
                                       str(self.session.get('id', '0')),
                                       self.context.get('is_admin', False))
        context['item_count'] = len(context.get('themes', 0))
            
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
