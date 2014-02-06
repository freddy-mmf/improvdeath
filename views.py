import os
from functools import wraps

import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users

from models import Show, Player, Death, DeathInterval


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
		self.context = {'image_path': self.app.registry.get('images'),
		                'css_path': self.app.registry.get('css'),
		                'js_path': self.app.registry.get('js'),
		                'is_admin': users.is_current_user_admin(),
						'user': user,
						'auth_url': auth_url,
						'auth_action': auth_action}
	
	def path(self, filename):
		return os.path.join(self.app.registry.get('templates'), filename)

		
class MainPage(ViewBase):
	def get(self):
		context = {}
		self.response.out.write(template.render(self.path('home.html'),
												self.context))


@login_required
class ShowRunPage(ViewBase):
	def get(self):
		context = {}
		self.response.out.write(template.render(self.path('show_run.html'),
												self.context))


class PreviousShowPage(ViewBase):
	def get(self, show_id):
		
		context = {}
		self.response.out.write(template.render(self.path('show_run.html'),
												self.context))