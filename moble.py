import cgi, wsgiref.handlers
import logging
import os, re
from google.appengine.api import users, urlfetch, images
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template

################################################################################
class MainPage(webapp.RequestHandler):
  def get(self):
    user = verify_login(self)
    if not user:
	    return
	    
    bookmarks = db.GqlQuery("SELECT * FROM Bookmark WHERE owner = :1 ORDER BY order, title LIMIT 10", user)
    
    DrawHeader(self, user, '/add', 'Add')
    template_values = {
      'bookmarks':bookmarks,
      }
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))
    DrawFooter(self)

################################################################################
class ShowBookmarks(webapp.RequestHandler):
  def get(self, path):
    shortcut = db.GqlQuery("SELECT * FROM PageShortcut WHERE path = :1", path).get()
    if not shortcut:
      self.redirect(users.create_login_url(self.request.uri))
      return
    
    bookmarks = db.GqlQuery("SELECT * FROM Bookmark WHERE owner = :1 ORDER BY order, title LIMIT 10", shortcut.owner)
    
    DrawHeader(self, None, '', '')
    template_values = {
      'bookmarks':bookmarks,
      }
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))
    DrawFooter(self)

################################################################################
class AddBookmark(webapp.RequestHandler):
  def get(self):
    user = verify_login(self)
    if not user:
	    return
	  
    DrawHeader(self, user, '/', 'Done')
    template_values = { }
    path = os.path.join(os.path.dirname(__file__), 'addbookmark.html')
    self.response.out.write(template.render(path, template_values))
    DrawFooter(self)
  
  def post(self):
    user = verify_login(self)
    if not user:
	    return
	
    bookmark = Bookmark()
    bookmark.owner = user
    bookmark.url = self.request.get('url')
    bookmark.title = self.request.get('title')
    load_image(bookmark)
    order = self.request.get('order')
    
    if order and int(order):
      bookmark.order = int(order)
    
    bookmark.put()
    self.redirect('/add')

################################################################################
class Settings(webapp.RequestHandler):
  def get(self):
    user = verify_login(self)
    if not user:
	    return    

    shortcut = db.GqlQuery("SELECT * FROM PageShortcut WHERE owner = :1", user).get()
    if not shortcut:
      shortcut = PageShortcut()
      shortcut.owner = user
      shortcut.path = user.nickname()
      shortcut.put()
    
    template_values = { 'shortcut_path' : shortcut.path }
    
    DrawHeader(self, user, '/', 'Done')
    path = os.path.join(os.path.dirname(__file__), 'settings.html')
    self.response.out.write(template.render(path, template_values))
    DrawFooter(self)
  
  def post(self):
    user = verify_login(self)
    if not user:
	    return
	
    new_shortcut = db.GqlQuery("SELECT * FROM PageShortcut WHERE path = :1", self.request.get('shortcut_path')).get()
    if new_shortcut and new_shortcut.owner != user:    # this shortcut is taken
      self.redirect('/settings')
      return
    
    shortcut = db.GqlQuery("SELECT * FROM PageShortcut WHERE owner = :1", user).get()
    shortcut.path = self.request.get('shortcut_path')
    shortcut.put()
    self.redirect('/' + shortcut.path)

################################################################################
class ShowIcon(webapp.RequestHandler):
  def get(self):
    bookmark = db.get(self.request.get("bmid"))
    if bookmark.icon:
      self.response.headers['Content-Type'] = "image/png"
      self.response.out.write(bookmark.icon)
    else:
      # self.redirect('/res/bm.png')
      self.error(404)

################################################################################
# functions
################################################################################
def verify_login(page):
    user = users.get_current_user()
    if not user:
      page.redirect(users.create_login_url(page.request.uri))
      return
    return user	

################################################################################
def load_image(bookmark):
  result = urlfetch.fetch(bookmark.url)
  url = host_part(bookmark.url) + '/favicon.ico'
  if result.status_code == 200:
    reattr = '((\w*=\w*".*?")|(\w*=\w*\'.*?\')|(\w*=\w*\s+)|())'
    hrefs = re.compile('<link\s+'+reattr+'*\s*rel="(shortcut )?icon"\s+'+reattr+'[^<>]*>', re.I).search(result.content,0)
    if hrefs:
      for m in hrefs.groups():
        if m:
          attr = m.split('=')
          logging.debug('m: ' + m)
          if 'href' == attr[0]:
            url = attr[1].strip('"')
            url = url.strip("'")
            url = normalize_url(url, bookmark.url)
            logging.debug('url: ' + url)
  
  result = urlfetch.fetch(url)
  if url:
    result = urlfetch.fetch(url)
    if result.status_code == 200 and result.headers['Content-Type'] != "text/html":
      img = images.resize(result.content, width=64, height=64, output_encoding=images.PNG)
      bookmark.icon = result.content

################################################################################
def normalize_url(url, base):
  if re.compile('^https?://', re.I).search(url, 0):
    return url
  if re.compile('^/').search(url, 0):
    return host_part(base) + url
  return base + '/' + url

################################################################################
def host_part(url):
  base = re.compile('^(https?://[\.A-Za-z0-9]+)', re.I).search(url, 0)
  if base:
    return base.group(1)

################################################################################
def DrawHeader(page, user, linkto, linktext):
  if user:
    logout_url = users.create_logout_url(page.request.uri)
  else:
	  logout_url = ''
	
  template_values = { 'linkto' : linkto,
		      'linktext' : linktext,
		      'logout_url' : logout_url }
  path = os.path.join(os.path.dirname(__file__), 'header.html')
  page.response.out.write(template.render(path, template_values))

################################################################################
def DrawFooter(page):
  template_values = { }
  path = os.path.join(os.path.dirname(__file__), 'footer.html')
  page.response.out.write(template.render(path, template_values))

################################################################################
# models
################################################################################
class Bookmark(db.Model):
  owner = db.UserProperty()
  title = db.StringProperty()
  url = db.LinkProperty()
  icon = db.BlobProperty()
  order = db.IntegerProperty()

class PageShortcut(db.Model):
  path = db.StringProperty()
  owner = db.UserProperty()

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication(
                                   [('/add', AddBookmark),
				                    ('/icon', ShowIcon),
				                    ('/settings', Settings),
				                    (r'/(.+)',ShowBookmarks),
				                    ('/', MainPage)],
                                    debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()


