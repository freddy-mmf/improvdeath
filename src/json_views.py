import json
import datetime

from google.appengine.ext import ndb

from views_base import ViewBase
from models import (Show)
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


class UpvoteJSON(ViewBase):
    def get(self):
    	response_dict = {}
    	if self.context.get('show_today'):
    		response_dict['item_count'] = Action.query(Action.used == False).count()
    	else:
    		response_dict['item_count'] = Theme.query(Theme.used == False).count()
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(response_dict))
    
    def post(self):
    	# Get the posted data
    	posted_id = self.request.get('id', '')
    	session_id = self.request.get('session_id')
    	# Splits the id into type and item id
    	item_type, item_id = posted_id.split('-')
    	if item_type == 'action':
    		item = ndb.Key(Action, int(item_id)).get()
    	else:
    		item = ndb.Key(Theme, int(item_id)).get()
        # See if the user already voted for this item
        if not session_id in item.get_voted_sessions:
        	# if the voted item was an action
            if item_type == 'action':
            	ActionVote(action=item.key, session_id=session_id).put()
            else:
            	ThemeVote(theme=item.key, session_id=session_id).put()
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps({}))