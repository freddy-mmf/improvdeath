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


class IntervalTimerJSON(ViewBase):
    def get(self, show_id):
    	time_json = {}
    	show = ndb.Key(Show, int(show_id)).get()
    	interval_gap = show.get_interval_gap(show.current_interval)
    	if interval_gap:
    		# Set the end of this gap
    		gap_end = back_to_tz(show.interval_vote_init) + datetime.timedelta(minutes=interval_gap)
        else:
            gap_end = back_to_tz(get_mountain_time())
        time_json.update({'hour': gap_end.hour,
                          'minute': gap_end.minute,
                          'second': gap_end.second})
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(time_json))
