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
        vote_options = show.current_vote_options(show)
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(vote_options))
