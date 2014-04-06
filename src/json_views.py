import json
import datetime

from google.appengine.ext import ndb

from views_base import ViewBase
from models import (Show, Action, LiveActionVote, Item, WildcardCharacter,
                    RoleVote, VOTE_AFTER_INTERVAL)
from timezone import get_mountain_time, back_to_tz


class ShowJSON(ViewBase):
    def get(self, show_id):
        show = ndb.Key(Show, int(show_id)).get()
        # If the interval show is running
        if show.running:
            vote_options = show.current_action_options()
        else:
            vote_options = show.current_vote_options()
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(vote_options))
