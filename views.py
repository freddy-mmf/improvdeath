import os
import json
import datetime
from functools import wraps

import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import ndb

from models import Show, Player, Death, ShowPlayer, ShowDeath, CauseOfDeath


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
		            'audio_path': self.app.registry.get('audio'),
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
		# Get today's and tomorrow's start time
		today = datetime.date.today()
		today_start = datetime.datetime.fromordinal(today.toordinal())
		tomorrow = datetime.date.today() + datetime.timedelta(1)
		tomorrow_start = datetime.datetime.fromordinal(tomorrow.toordinal())
		
		# Get the current show
		current_show = Show.query(
			Show.scheduled > today_start,
			Show.scheduled < tomorrow_start,).order(Show.scheduled).get()

		# Get the previous shows
		previous_shows = Show.query(
			Show.scheduled < today_start).order(Show.scheduled).filter()
		context = {'current_show': current_show,
				   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class ShowPage(ViewBase):
	def get(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		context	= {'show': show,
				   'host_url': self.request.host_url}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))
	@admin_required
	def post(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		if self.request.get('start_show'):
			show.start_time = datetime.datetime.now()
			show.put()
		context	= {'show': show,
				   'host_url': self.request.host_url}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context()))

class CreateShow(ViewBase):
	@admin_required
	def get(self):
		context = {'players': Player.all().run()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		length = int(self.request.get('show_length'))
		scheduled_string = self.request.get('scheduled')
		player_list = self.request.get_all('player_list')
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
				player = ndb.Key(urlsafe=player)
				ShowPlayer(show=show, player=player).put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))


class ShowJSON(ViewBase):
	def get(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		show_obj = {'event': 'default'}
		if show.running:
			now = datetime.datetime.now()
			# Within first 10 seconds of show starting
			first_ten_end = show.start_time + datetime.timedelta(seconds=10)
			# If we're within the first 10 seconds of the show
			if now >= show.start_time and now <= first_ten_end:
				show_obj = {'event': 'init-players'}
			else:
				for death in show.deaths:
					thirty_after_interval = death.time_of_death + datetime.timedelta(
																			seconds=30)
					if now >= death.time_of_death and now <= thirty_after_interval:
						show_obj = {'event': 'player-death',
								    'player_photo': death.player.photo_filename}
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(show_obj))


class DeathPool(ViewBase):
	def get(self):
		current_deaths = CauseOfDeath.query(
			CauseOfDeath.created_date == datetime.datetime.today(),
			CauseOfDeath.used == False).fetch()
		previous_deaths = CauseOfDeath.query(
			CauseOfDeath.created_date < datetime.datetime.today(),
			CauseOfDeath.used == False).fetch()
		context = {'current_death_pool': current_deaths,
				   'previous_death_pool': previous_deaths}
		self.response.out.write(template.render(self.path('death_pool.html'),
												self.add_context(context)))

	def post(self):
		context = {}
		cod = None
		cause = self.request.get('cause')
		current_death_list = self.request.get_all('current_death_list')
		previous_death_list = self.request.get_all('previous_death_list')
		if cause:
			cod = CauseOfDeath(cause=cause).put().get()
			context['created'] = True
		elif current_death_list:
			for death in current_death_list:
				death_key = ndb.Key(CauseOfDeath, int(death)).get()
				death_key.key.delete()
			context['cur_deleted'] = True
		elif previous_death_list:
			for death in previous_death_list:
				death_key = ndb.Key(CauseOfDeath, int(death)).get()
				death_key.key.delete()
			context['prev_deleted'] = True
		context['current_death_pool'] = CauseOfDeath.query(
			CauseOfDeath.created_date == datetime.datetime.today(),
			CauseOfDeath.used == False).fetch()
		if cod:
			context['current_death_pool'].append(cod)
		context['previous_death_pool'] = CauseOfDeath.query(
			CauseOfDeath.created_date < datetime.datetime.today(),
			CauseOfDeath.used == False).fetch()
		self.response.out.write(template.render(self.path('death_pool.html'),
												self.add_context(context)))
