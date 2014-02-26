import os
import json
import datetime
from functools import wraps

import webapp2

from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import ndb

from models import Show, Player, Death, ShowPlayer, ShowDeath, CauseOfDeath

from timezone import mountain_time, get_mountain_time, today


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not users.is_current_user_admin():
            return webapp2.redirect(
        			users.create_login_url(webapp2.get_request().url))
        return func(*args, **kwargs)
    return decorated_view


def get_today_start():
	return datetime.datetime.fromordinal(today.toordinal())


def get_tomorrow_start():
	tomorrow = today + datetime.timedelta(1)
	return datetime.datetime.fromordinal(tomorrow.toordinal())


def show_today():
	# See if there is a show today, otherwise users aren't allowed to submit deaths
	today_start = get_today_start()
	tomorrow_start = get_tomorrow_start()
	return bool(Show.query(
		Show.scheduled > today_start,
		Show.scheduled < tomorrow_start).get())


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
		            'player_image_path': self.app.registry.get('player_images'),
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
		today_start = get_today_start()
		tomorrow_start = get_tomorrow_start()

		# Get the current show
		current_show = Show.query(
			Show.scheduled > today_start,
			Show.scheduled < tomorrow_start).order(Show.scheduled).get()
		# Get the future shows
		future_shows = Show.query(
			Show.scheduled > tomorrow_start).order(Show.scheduled).filter()
		# Get the previous shows
		previous_shows = Show.query(
			Show.scheduled < today_start).order(Show.scheduled).filter()
		context = {'current_show': current_show,
				   'future_shows': future_shows,
				   'previous_shows': previous_shows}
		self.response.out.write(template.render(self.path('home.html'),
												self.add_context(context)))


class ShowPage(ViewBase):
	def get(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		available_causes = len(CauseOfDeath.query(
							   CauseOfDeath.used == False).fetch())
		context	= {'show': show,
				   'available_causes': available_causes,
				   'host_url': self.request.host_url}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))

	@admin_required
	def post(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		if self.request.get('start_show'):
			show.start_time = mountain_time
			show.put()
		context	= {'show': show,
				   'host_url': self.request.host_url}
		self.response.out.write(template.render(self.path('show.html'),
												self.add_context(context)))

class CreateShow(ViewBase):
	@admin_required
	def get(self):
		context = {'players': Player.query().fetch()}
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		length = int(self.request.get('show_length'))
		scheduled_string = self.request.get('scheduled')
		theme = self.request.get('theme')
		player_list = self.request.get_all('player_list')
		death_intervals = self.request.get('death_intervals')
		show_style = self.request.get('show_style')
		context = {'players': Player.query().fetch()}
		if length and player_list and death_intervals:
			# Get the list of interval times
			try:
				interval_list = [int(x.strip()) for x in death_intervals.split(',')]
			except ValueError:
				raise ValueError("Invalid interval list '%s'. Must be comma separated.")
			# If there are more death intervals than players, raise an error
			if len(interval_list) > len(player_list):
				raise ValueError("Not enough players for death intervals.")
			if scheduled_string:
				scheduled = datetime.datetime.strptime(scheduled_string,
													   "%d.%m.%Y %H:%M")
			else:
				scheduled = mountain_time
			show = Show(length=length, scheduled=scheduled,
						theme=theme, show_style=show_style).put()
			# Add the death intervals to the show
			for interval in interval_list:
				death = Death(interval=interval).put()
				ShowDeath(show=show, death=death).put()
			# Add the players to the show
			for player in player_list:
				player_key = ndb.Key(Player, int(player)).get().key
				ShowPlayer(show=show, player=player_key).put()
			context['created'] = True
		self.response.out.write(template.render(self.path('create_show.html'),
												self.add_context(context)))


class DeleteShows(ViewBase):
	@admin_required
	def get(self):
		context = {'shows': Show.query().fetch()}
		self.response.out.write(template.render(self.path('delete_shows.html'),
												self.add_context(context)))

	@admin_required
	def post(self):
		show_id = int(self.request.get('show_id'))
		show = ndb.Key(Show, int(show_id))
		show_deaths = ShowDeath.query(ShowDeath.show == show).fetch()
		for show_death in show_deaths:
			cause = show_death.death.get().cause
			if cause:
				cause.delete()
			show_death.death.delete()
			show_death.key.delete()
		show_players = ShowPlayer.query(ShowPlayer.show == show).fetch()
		for show_player in show_players:
			show_player.key.delete()
		show.delete()
		context = {'deleted': True,
				   'shows': Show.query().fetch()}
		self.response.out.write(template.render(self.path('delete_shows.html'),
												self.add_context(context)))


class AddPlayers(ViewBase):
	@admin_required
	def get(self):
		self.response.out.write(template.render(self.path('add_players.html'),
												self.add_context()))

	@admin_required
	def post(self):
		created = False
		player_name = self.request.get('player_name')
		photo_filename = self.request.get('photo_filename')
		date_added = self.request.get('date_added')
		if player_name and photo_filename:
			if date_added:
				date_added = datetime.datetime.strptime(scheduled_string,
													   "%d.%m.%Y %H:%M")
			else:
				date_added = mountain_time
			Player(name=player_name,
				   photo_filename=photo_filename,
				   date_added=date_added).put()
			created = True
		context = {'created': created}
		self.response.out.write(template.render(self.path('add_players.html'),
												self.add_context(context)))
			

class ShowJSON(ViewBase):
	def get(self, show_key):
		show = ndb.Key(Show, int(show_key)).get()
		show_obj = {'event': 'default-screen'}
		if show.running:
			now = get_mountain_time()
			# Within first 10 seconds of show starting
			first_ten_end = show.start_time + datetime.timedelta(seconds=10)
			# If we're within the first 10 seconds of the show
			if now >= show.start_time and now <= first_ten_end:
				show_obj = {'event': 'init-players'}
			else:
				for death in show.deaths:
					thirty_after_interval = death.time_of_death + datetime.timedelta(
																			seconds=30)
					print "thirty_after_interval, ", thirty_after_interval
					print "death.time_of_death, ", death.time_of_death
					if now >= death.time_of_death and now <= thirty_after_interval:
						player_entity = death.player.get()
						show_obj = {'event': 'player-death',
								    'player_photo': player_entity.photo_filename,
								    'cause': death.cause.get().cause}
		self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		self.response.out.write(json.dumps(show_obj))


class DeathPool(ViewBase):
	def get(self):
		current_deaths = CauseOfDeath.query(
			CauseOfDeath.created_date == today,
			CauseOfDeath.used == False).fetch()
		previous_deaths = CauseOfDeath.query(
			CauseOfDeath.created_date < today,
			CauseOfDeath.used == False).fetch()
		context = {'current_death_pool': current_deaths,
				   'previous_death_pool': previous_deaths,
				   'show_today': show_today()}
		self.response.out.write(template.render(self.path('death_pool.html'),
												self.add_context(context)))

	def post(self):
		context = {'show_today': show_today()}
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
			CauseOfDeath.created_date == today,
			CauseOfDeath.used == False).fetch()
		if cod:
			context['current_death_pool'].append(cod)
		context['previous_death_pool'] = CauseOfDeath.query(
			CauseOfDeath.created_date < today,
			CauseOfDeath.used == False).fetch()
		self.response.out.write(template.render(self.path('death_pool.html'),
												self.add_context(context)))
