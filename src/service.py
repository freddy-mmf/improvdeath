from google.appengine.ext import ndb

from models import (Show, Player, VoteType, Suggestion, PreshowVote,
                    ShowInterval, VoteOptions, LiveVote, SuggestionPool,
                    VotedItem, get_current_show, VOTE_STYLE, OCCURS_TYPE)
from timezone import (get_today_start, get_tomorrow_start)


def show_today():
    # See if there is a show today, otherwise users aren't allowed to submit actions
    today_start = get_today_start()
    tomorrow_start = get_tomorrow_start()
    return bool(Show.query(Show.created >= today_start,
                           Show.created < tomorrow_start).get())


def get_show(**kwargs):
    return get_model_entity(Show, **kwargs)


def get_vote_type(**kwargs):
    return get_model_entity(VoteType, **kwargs)


def get_player(**kwargs):
    return get_model_entity(Player, **kwargs)


def get_suggestion(**kwargs):
    return get_model_entity(Suggestion, **kwargs)

def get_suggestion_pool(**kwargs):
    return get_model_entity(SuggestionPool, **kwargs)

def get_model_entity(model, key_id=None, name=None):
    # If key id is given, just return the key
    if key_id:
        return ndb.Key(model, int(key_id)).get()
    args = []
    if name:
        args.append(model.name == name)
    return model.query(*args).get()


def fetch_shows(**kwargs):
    return fetch_model_entities(Show, **kwargs)


def fetch_suggestions(**kwargs):
    return fetch_model_entities(Suggestion, **kwargs)


def fetch_players(**kwargs):
    return fetch_model_entities(Player, **kwargs)


def fetch_vote_types(**kwargs):
    return fetch_model_entities(VoteType, **kwargs)

def fetch_suggestion_pools(**kwargs):
    return fetch_model_entities(SuggestionPool, **kwargs)

def fetch_preshow_votes(**kwargs):
    return fetch_model_entities(PreshowVote, **kwargs)


def fetch_vote_options(**kwargs):
    return fetch_model_entities(VoteOptions, **kwargs)


def fetch_live_votes(**kwargs):
    return fetch_model_entities(LiveVote, **kwargs)


def fetch_voted_items(**kwargs):
    return fetch_model_entities(VotedItem, **kwargs)


def fetch_show_intervals(**kwargs):
    return fetch_model_entities(ShowInterval, **kwargs)


def fetch_model_entities(model, show=None, vote_type=None, suggestion_pool=None,
                         used=None, voted_on=None,
                         suggestion=None, uses_suggestions=None,
                         limit=None, offset=None, keys_only=False,
                         order_by_vote_value=False, delete=False):
    args = []
    fetch_args = {}
    ordering = None
    # Fetch by show key
    if show:
        args.append(model.show == show)
    # Fetch by VoteType name
    if vote_type:
        args.append(model.vote_type == vote_type)
    # Fetch by SuggestionPool
    if suggestion_pool:
        args.append(model.suggestion_pool == suggestion_pool)
    # Fetch by whether it's used or not
    if used != None:
        args.append(model.used == used)
    # Fetch by whether it's been voted on or not
    if voted_on != None:
        args.append(model.voted_on == voted_on)
    # Fetch related to a suggestion
    if suggestion != None:
        args.append(model.suggestion == suggestion)
    # Fetch related to a suggestion
    if uses_suggestions != None:
        args.append(model.uses_suggestions == uses_suggestions)
    
    # Delete the queried items
    if delete:
        item_keys = model.query(*args).fetch(keys_only=True)
        # Delete all the items
        ndb.delete_multi(item_keys)
        return
    
    # Fetch the limit given
    if limit:
        fetch_args['limit'] = limit
    # If we just need the keys
    if keys_only:
        fetch_args['keys_only'] = keys_only
    
    # Order by vote_value
    if order_by_vote_value:
        ordering = [-model.vote_value]
        
    if ordering:
        return model.query(*args).order(*ordering).fetch(**fetch_args)
    else:
        return model.query(*args).fetch(**fetch_args)


def create_show(create_data):
    return create_model_entity(Show, create_data)


def create_player(create_data):
    return create_model_entity(Player, create_data)


def create_show_interval(create_data):
    return create_model_entity(ShowInterval, create_data)


def create_vote_type(create_data):
    return create_model_entity(VoteType, create_data)


def create_suggestion_pool(create_data):
    return create_model_entity(SuggestionPool, create_data)


def create_live_vote(create_data):
    return create_model_entity(LiveVote, create_data)


def create_model_entity(model, create_data):
    create_kwargs = {}
    for key, value in create_data.items():
        create_kwargs[key] = value
    return model(**create_kwargs).put()


def get_live_vote_exists(show, vote_type, interval, session_id, suggestion=None,
                         player=None):
    return bool(LiveVote.query(
                    LiveVote.suggestion == suggestion,
                    LiveVote.player == player,
                    LiveVote.show == show,
                    LiveVote.vote_type == vote_type,
                    LiveVote.interval == interval,
                    LiveVote.session_id == str(session_id)).get())


def get_unused_suggestions():
    """Get unused suggestions for all vote types, categorized by vote type"""
    vote_types = fetch_vote_types()
    for vote_type in vote_types:
        suggestion_pool = vote_type.suggestion_pool
        suggestions = fetch_suggestions(suggestion_pool=suggestion_pool,
                                        used=False,
                                        voted_on=False)
        setattr(vote_type, 'suggestions', suggestions)
    return vote_types


def pre_show_voting_post(show_key, suggestion_pool, request, session_id, user_id, is_admin):
    context = {'session_id': session_id}
    suggestion_entity = None
    # Get the value of the entry that was added
    entry_value = request.get('entry_value')
    # Get the upvote
    upvote = request.get('upvote')
    # If a delete was requested on an entry
    delete_id = request.get('delete_id')
    # If this is a brand new entry
    if entry_value:
        # Create the suggestion
        suggestion_entity = Suggestion(value=entry_value,
                                       show=show,
                                       suggestion_pool=suggestion_pool.key,
                                       preshow_value=0,
                                       session_id=session_id,
                                       user_id=user_id).put().get()
        context['created'] = True
    elif upvote:
        suggestion_key = ndb.Key(Suggestion, int(upvote)).get().key
        # Get the pre-show vote if it exists for that suggestion and session id
        pv = PreshowVote.query(
                PreshowVote == suggestion_key,
                PreshowVote.session_id == session_id).get()
        # If it doesn't exist, create it
        if not pv:
            PreshowVote(show=show,
                        suggestion=suggestion_key,
                        session_id=session_id).put()
    # If a delete was requested
    elif delete_id:
        # Fetch the suggestion entity
        suggestion_entity = ndb.Key(Suggestion, int(delete_id)).get()
        # Make sure the entry was either the session id that created it
        # Or this is an admin user
        if session_id == suggestion_entity.session_id or is_admin:
            suggestion_entity.key.delete()
    
    # If an new suggestion entity was created
    if suggestion_entity:
        # Have to sort first by suggestion key, since we query on it. Dumb...
        suggestion_entities = Suggestion.query(Suggestion.used == False,
                                               Suggestion.key != suggestion_entity.key,
                                               ).fetch()
        suggestion_entities.sort(key=lambda x: (x.preshow_value, x.created), reverse=True)
        # If the entity wasn't deleted
        if not delete_id:
            # Add the newly added suggestion entity
            suggestion_entities.append(suggestion_entity)
    else:
        suggestion_entities = Suggestion.query(Suggestion.used == False,
                                   ).order(-Suggestion.preshow_value,
                                     Suggestion.created).fetch()
    context['suggestions'] = suggestion_entities
    
    return context
