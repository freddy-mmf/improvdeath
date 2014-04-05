#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#import sys
#for p in ['gaepytz-2011h.zip']:
#    sys.path.insert(0, p)

import os
import webapp2

from views_base import RobotsTXT
from user_views import (MainPage, LiveVote, AddActions, AddThemes,
						AddItems, AddCharacters, OtherShows)
from admin_views import (ShowPage, CreateShow, DeleteTools,
					     JSTestPage, AddPlayers)
from json_views import (ActionsJSON, CurrentTime, ShowJSON)


config= {'webapp2_extras.sessions': {
    	     'secret_key': '8djs1qjs3jsm'
    	     }
    	}


app = webapp2.WSGIApplication([
	# Robots.txt
	(r'/robots.txt', RobotsTXT),
	# User pages
    (r'/', MainPage),
    (r'/show/(\d+)/', ShowPage),
    (r'/live_vote/', LiveVote),
    (r'/add_actions/', AddActions),
    (r'/add_items/', AddItems),
    (r'/add_characters/', AddCharacters),
    (r'/add_themes/', AddThemes),
    (r'/other_shows/$', OtherShows),
    (r'/other_shows/(\d+)/', OtherShows),
    # Admin URLS
    (r'/create_show/', CreateShow),
    (r'/add_players/', AddPlayers),
    (r'/delete_tools/', DeleteTools),
    (r'/js_test/', JSTestPage),
    # JSON ENDPOINT
    (r'/show_json/(\d+)/', ShowJSON),
],
  config=config,
  debug=True)


app.registry['templates'] = os.path.join(os.path.dirname(__file__),
										 'templates/')
app.registry['images'] = os.path.join(os.path.dirname(__file__),
										 '/static/img/')
app.registry['player_images'] = os.path.join(os.path.dirname(__file__),
										 '/static/img/players/')
app.registry['css'] = os.path.join(os.path.dirname(__file__),
										 '/static/css/')
app.registry['js'] = os.path.join(os.path.dirname(__file__),
										 '/static/js/')
app.registry['audio'] = os.path.join(os.path.dirname(__file__),
										 '/static/audio/')

