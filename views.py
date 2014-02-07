import os
import datetime
from functools import wraps

import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db

from models import Show, Player, Death


def login_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.get_current_user():
            return webapp2.redirect(
        			users.create_login_url(webapp2.get_request().url))
        return func(*args, **kwargs)
    return decorated_view


class ViewBase(webapp2.RequestHandler):
	def __init__(self, *args, **kwargs):
		super(ViewBase, self).__init__(*args, **kwargs)
		self.app = webapp2.get_app()
		user = users.get_current_user()
		if users.get_current_user():
			auth_url = users.create_logout_url(self.request.uri)
			auth_action = 'Logout'
		else:
			auth_url = users.create_login_url(self.request.uri)
			auth_action = 'Login'
		self.context = {
				    'image_path': self.app.registry.get('images'),
		            'css_path': self.app.registry.get('css'),
		            'js_path': self.app.registry.get('js'),
		            'is_admin': users.is_current_user_admin(),
					'user': user,
					'auth_url': auth_url,
					'auth_action': auth_action}
	
	def add_context(self, add_context={}):
		self.context.update(add_context)
		return self.context
	
	def path(self, filename):
		return os.path.join(self.app.registry.get('templates'), filename)

		
class MainPage(ViewBase):
	def get(self):
		q = Show.all()
		shows = q.run()
		context = {'shows': shows}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class ShowPage(ViewBase):
	def get(self, show_key):
		show = db.Key(encoded=show_key)
		context	= {'show': show}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))
	@login_required
	def post(self, show_key):
		show = db.Key(encoded=show_key)
		if self.request.get('start_show'):
			Death(show=show,
				  interval=5,
				 ).put()
			show.start_time=datetime.datetime.now()
			show.put()
			player_key = Player(name='Freddy',
				   photo_filename='freddy.jpg',
				   date_added=datetime.datetime.now(),
				).put()
			show.players.append(player_key)
		context	= {'show': show}
		self.response.out.write(template.render(self.path('show_run.html'),
												self.add_context()))
