from models import (Show, Player, PoolType, Suggestion, PreshowVote,
                    ShowPlayerInterval, VoteOptions, LiveVote,
                    VotedItem)
#from models import (VOTE_AFTER_INTERVAL, ROLE_TYPES, VOTE_TYPES)
from timezone import (get_today_start, get_tomorrow_start)



def get_current_show():
	return Show.query(
			Show.scheduled >= get_today_start(),
			Show.scheduled < get_tomorrow_start()).order(-Show.scheduled).get()


def show_today():
	# See if there is a show today, otherwise users aren't allowed to submit actions
	today_start = get_today_start()
	tomorrow_start = get_tomorrow_start()
	return bool(Show.query(Show.scheduled >= today_start,
						   Show.scheduled < tomorrow_start).get())


def get_show(**kwargs):
    return get_model_entity(Show, **kwargs)


def get_pool_type(**kwargs):
    return get_model_entity(PoolType, **kwargs)


def get_player(**kwargs):
    return get_model_entity(Player, **kwargs)


def get_suggestion(**kwargs):
    return get_model_entity(Suggestion, **kwargs)


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
    return fetch_model_entities(Players, **kwargs)


def fetch_pool_types(**kwargs):
    return fetch_model_entities(PoolType, **kwargs)
    

def fetch_preshow_votes(**kwargs):
    return fetch_model_entities(PreshowVote, **kwargs)


def fetch_vote_options(**kwargs):
    return fetch_model_entities(VoteOptions, **kwargs)


def fetch_live_votes(**kwargs):
    return fetch_model_entities(LiveVote, **kwargs)


def fetch_voted_items(**kwargs):
    return fetch_model_entities(VotedItem, **kwargs)


def fetch_showplayerinterval(**kwargs):
    return fetch_model_entities(ShowPlayerInterval, **kwargs)


def fetch_model_entities(model, show=None, pool_type=None, used=None, live=None,
                         suggestion=None, uses_suggestions=None,
                         limit=None, offset=None, keys_only=False,
                         order_by_vote_value=False):
    args = []
    fetch_args = {}
    ordering = None
    # Fetch by show key
    if show:
        args.append(model.show == show)
    # Fetch by PoolType name
    if pool_type:
        args.append(model.pool_type == get_pool_type(name=pool_type))
    # Fetch by whether it's used or not
    if used != None:
        args.append(model.used == used)
    # Fetch by whether it's live or not
    if live != None:
        args.append(model.live == live)
    # Fetch related to a suggestion
    if suggestion != None:
        args.append(model.suggestion == suggestion)
    # Fetch related to a suggestion
    if uses_suggestions != None:
        args.append(model.uses_suggestions == uses_suggestions)
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


def create_show(**kwargs):
    return create_model_entity(Show, **kwargs)


def create_showplayerinterval(**kwargs)
    return create_model_entity(ShowPlayerInterval, **kwargs)


def create_model_entity(model, **kwargs):
    create_kwargs = {}
    for key, value in kwargs.items():
        create_kwargs[key] = value
    return model(**create_kwargs).put()
