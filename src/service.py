from models import (Show, Player, VoteType, Suggestion, PreshowVote,
                    ShowInterval, VoteOptions, LiveVote, SuggestionPool,
                    VotedItem, get_current_show, VOTE_STYLE, OCCURS_TYPE)
from timezone import (get_today_start, get_tomorrow_start)


def show_today():
	# See if there is a show today, otherwise users aren't allowed to submit actions
	today_start = get_today_start()
	tomorrow_start = get_tomorrow_start()
	return bool(Show.query(Show.scheduled >= today_start,
						   Show.scheduled < tomorrow_start).get())


def get_show(**kwargs):
    return get_model_entity(Show, **kwargs)


def get_vote_type(**kwargs):
    return get_model_entity(VoteType, **kwargs)


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


def fetch_vote_types(**kwargs):
    return fetch_model_entities(VoteType, **kwargs)

def fetch_suggestion_pools(**kwargs):
    return fetch_model_entities(VoteType, **kwargs)

def fetch_preshow_votes(**kwargs):
    return fetch_model_entities(PreshowVote, **kwargs)


def fetch_vote_options(**kwargs):
    return fetch_model_entities(VoteOptions, **kwargs)


def fetch_live_votes(**kwargs):
    return fetch_model_entities(LiveVote, **kwargs)


def fetch_voted_items(**kwargs):
    return fetch_model_entities(VotedItem, **kwargs)


def fetch_showinterval(**kwargs):
    return fetch_model_entities(ShowInterval, **kwargs)


def fetch_model_entities(model, show=None, vote_type=None, used=None, live=None,
                         suggestion=None, uses_suggestions=None,
                         limit=None, offset=None, keys_only=False,
                         order_by_vote_value=False):
    args = []
    fetch_args = {}
    ordering = None
    # Fetch by show key
    if show:
        args.append(model.show == show)
    # Fetch by VoteType name
    if vote_type:
        args.append(model.vote_type == get_vote_type(name=vote_type))
    # Fetch by whether it's used or not
    if used != None:
        args.append(model.used == used)
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


def create_showinterval(**kwargs)
    return create_model_entity(ShowInterval, **kwargs)


def create_vote_type(**kwargs)
    return create_model_entity(VoteType, **kwargs)


def create_suggestion_pool(**kwargs)
    return create_model_entity(SuggestionPool, **kwargs)


def create_model_entity(model, **kwargs):
    create_kwargs = {}
    for key, value in kwargs.items():
        create_kwargs[key] = value
    return model(**create_kwargs).put()


def reset_live_votes():
    """
       Reset all suggestions that haven't been used,
       but have a live_vote_value, to zero
    """
    suggestions = Suggestion.query(Suggestion.live_value > 0
                                   Suggestion.used == False).fetch()
    for suggestion in suggestions:
		# Set the suggestion live value to zero
		suggestion.live_value = 0
		suggestion.put()
