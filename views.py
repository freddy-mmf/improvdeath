import os
import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users


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


class MainAdmin(ViewBase):
	def get(self):
		context = {}
		self.response.out.write(template.render(self.path('admin/home.html'),
												self.context))