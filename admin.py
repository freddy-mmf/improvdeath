import os
import webapp2

from views import MainAdmin


app = webapp2.WSGIApplication([
    ('/', MainAdmin)
], debug=True)


app.registry['templates'] = os.path.join(os.path.dirname(__file__),
										 'templates/')
app.registry['images'] = os.path.join(os.path.dirname(__file__),
										 'static/images')
app.registry['css'] = os.path.join(os.path.dirname(__file__),
										 'static/css')
app.registry['js'] = os.path.join(os.path.dirname(__file__),
										 'static/js')	