''' generate a static version of grimoire.org '''
from grimoire import app
import os
from py2neo import authenticate, Graph
import re
import requests
import shutil

user = os.environ['NEO4J_USER']
password = os.environ['NEO4J_PASS']
authenticate('localhost:7474', user, password)

graph = Graph()
query = graph.cypher.execute

# get every category
labels = query('MATCH n RETURN DISTINCT LABELS(n)')
labels = [[m for m in list(l)[0] if not 'parent' in m][0] for l in labels]
labels = list(set(labels))

try:
    shutil.rmtree('_site')
except OSError:
    pass

rules = app.url_map._rules
urls = [r.rule for r in rules if \
        not '<' in r.rule and \
        not 'api/' in r.rule and \
        not 'compare' in r.rule]

# get every page for each category
for label in labels:
    nodes = query('MATCH (n:%s) RETURN n.uid' % label)
    urls.append('/%s' % label) # ensures index pages are added
    urls += ['/%s/%s' % (label, n[0]) for n in nodes]

redirects = open('redirects', 'w')
urls = list(set(urls))
for url in urls:
    page = requests.get('http://localhost:4080%s' % url, allow_redirects=False)
    if page.is_redirect:
        print 'redirecting %s' % url
        path = re.sub('http://localhost:4080', '', page.headers['Location'])
        redirects.write('''
    location = %s {
        return 301 %s;
    }''' % (url, path))
        continue

    print 'loading %s' % url
    try:
        os.makedirs('_site%s' % url)
    except OSError:
        pass

    rendered = open('_site%s/index.html' % url, 'w')
    rendered.write(page.text.encode('utf8'))
