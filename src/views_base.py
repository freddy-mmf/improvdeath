import os
import random
import datetime
from functools import wraps

import webapp2
from webapp2_extras import sessions
from google.appengine.api import users

from service import show_today, get_current_show
from timezone import get_mountain_time

LIVE_VOTE_URI = '/live_vote/'


def get_or_default(item, default):
    if item == '' or item == None:
        return default
    return item

def redirect_locked(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        show = get_current_show()
        if show and show.locked and not users.is_current_user_admin():
            return webapp2.redirect(LIVE_VOTE_URI, abort=True)
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
                    'host_domain': self.request.host_url.replace('http://', ''),
                    'image_path': self.app.registry.get('images'),
                    'css_path': self.app.registry.get('css'),
                    'js_path': self.app.registry.get('js'),
                    'audio_path': self.app.registry.get('audio'),
                    'player_image_path': self.app.registry.get('player_images'),
                    'is_admin': users.is_current_user_admin(),
                    'user': user,
                    'auth_url': auth_url,
                    'auth_action': auth_action,
                    'path_qs': self.request.path_qs,
                    'show_today': show_today(),
                    'current_show': get_current_show()}
    
    def add_context(self, add_context={}):
        self.context.update(add_context)
        return self.context
    
    def path(self, filename):
        return os.path.join(self.app.registry.get('templates'), filename)

    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        session = self.session_store.get_session()
        if not session.get('id'):
            # Get a random hash to store as the session id
            session['id'] = random.getrandbits(128)
        return session
  
    def current_user(self):
        """Returns currently logged in user"""
        return users.get_current_user()


class RobotsTXT(webapp2.RequestHandler):
    def get(self):
        # Set to not be indexed
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("User-agent: *\nDisallow: /")


class LoaderIO(webapp2.RequestHandler):
    def get(self):
        # Set to not be indexed
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("loaderio-9b6fa50492da1609dc61b9198b767688")