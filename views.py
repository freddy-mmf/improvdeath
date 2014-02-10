import os
import datetime
from functools import wraps

import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db

from models import Show, Player, Death, ShowPlayer, ShowDeath


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
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
		# Get the current show
		q = Show.all()
		q.filter("scheduled >=", datetime.datetime.now())
		q.order("scheduled")
		current_show = q.get()
		# Get the previous shows
		q = Show.all()
		q.filter("scheduled <", datetime.datetime.now())
		q.order("scheduled")
		previous_shows = q.run()
		context = {'current_show': current_show,
				   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class ShowPage(ViewBase):
	def get(self, show_key):
		show = db.Key(encoded=show_key)
		context	= {'show': show}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))
	@admin_required
	def post(self, show_key):
		show = db.Key(encoded=show_key)
		if self.request.get('start_show'):
			show.start_time = datetime.datetime.now()
			show.put()
		context	= {'show': show}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context()))

class CreateShow(ViewBase):
	def get(self):
		context = {'players': Player.all().run()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		length = int(self.request.get('show_length'))
		scheduled_string = self.request.get('scheduled')
		player_list = self.request.get('player_list', allow_multiple=True)
		death_intervals = self.request.get('death_intervals')
		context = {'players': Player.all().run()}
		print "length: %s scheduled: %s player_list: %s death_intervals: %s" % (
				length, scheduled_string, player_list, death_intervals)
		if length and player_list and death_intervals:
			if scheduled_string:
				scheduled = datetime.datetime.strptime(scheduled_string,
													   "%d.%m.%Y %H:%M")
			else:
				scheduled = None
			show = Show(length=length, scheduled=scheduled).put()
			# Get the list of interval times
			try:
				interval_list = [int(x.strip()) for x in death_intervals.split(',')]
			except ValueError:
				raise ValueError("Invalid interval list '%s'. Must be comma separated.")
			# Add the death intervals to the show
			for interval in interval_list:
				death = Death(interval=interval).put()
				ShowDeath(show=show, death=death).put()
			# Add the players to the show
			for player in player_list:
				print player
				player = db.Key(encoded=player)
				ShowPlayer(show=show, player=player).put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))