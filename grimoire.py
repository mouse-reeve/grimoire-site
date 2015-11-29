''' webserver for grimoire graph data '''
from werkzeug.exceptions import BadRequestKeyError
from flask import Flask, redirect, render_template, request
from graph_service import GraphService
import logging
import re

app = Flask(__name__)
graph = GraphService()


# ----- routes
@app.route('/', methods=['GET'])
def index():
    ''' render the basic template for angular '''
    data = graph.get_all('grimoire')
    grimoires = []
    for g in data['nodes']:
        g = g['properties']
        date = grimoire_date(g)

        grimoires.append({
            'uid': g['uid'],
            'identifier': g['identifier'],
            'date': date
        })
        grimoires = sorted(grimoires, key=lambda g: g['identifier'])
    return render_template('home.html', grimoires=grimoires, title='Grimoire Metadata')


@app.route('/random', methods=['GET'])
def random():
    ''' pick a node, any node '''
    data = graph.random()
    return redirect(data['nodes'][0]['link'])


@app.route('/index', methods=['GET'])
def content_index():
    ''' list everything available by category '''
    data = []
    for label in graph.get_labels():
        data.append({
            'label': label,
            'nodes': graph.get_all(label)['nodes']
        })
    return render_template('index.html', data=data, title='Index')


@app.route('/support', methods=['GET'])
def support():
    ''' the "give me money" page '''
    return render_template('support.html')


@app.route('/search', methods=['GET'])
def search():
    ''' look up a term '''
    try:
        term = sanitize(request.values['term'], allow_spaces=True)
    except BadRequestKeyError:
        return redirect('/')
    data = graph.search(term)
    return render_template('search.html', results=data['nodes'], term=term)


@app.route('/grimoire/<uid>', methods=['GET'])
def grimoire(uid):
    ''' grimoire page '''
    logging.info('loading grimoire: %s', uid)
    uid = sanitize(uid)
    data = graph.get_node(uid)

    node = data['nodes'][0]
    grim = {'id': node['id']}
    grim['date'] = grimoire_date(node['properties'])

    props = node['properties']
    if 'century' in props:
        del props['century']
    if 'decade' in props:
        del props['decade']
    if 'year' in props:
        del props['year']

    grim['properties'] = props
    grim['editions'] = [r for r in data['relationships']
                        if r['end']['label'] and r['end']['label'] == 'edition']


    grim['entities'] = {}
    entities = ['angel', 'demon', 'olympian_spirit', 'fairy']
    for entity in entities:
        grim['entities'][entity] = [r for r in data['relationships']
                                    if r['end']['label'] and r['end']['label'] == entity]

    grim['relationships'] = [r for r in data['relationships']
                             if not (r['end']['label']
                             and r['end']['label'] in (entities + ['edition']))]
    title = '%s (Grimoire)' % grim['properties']['identifier']
    return render_template('grimoire.html', data=grim, title=title)


@app.route('/fairy/<uid>', methods=['GET'])
def fairy(uid):
    uid = sanitize(uid)
    data = graph.get_node(uid)
    data['relationships'] = [r for r in data['relationships'] if
                             r['type'] != 'has_sister' or r['end']['id'] != data['nodes'][0]['id']]
    title = '%s (Fairy)' % data['nodes'][0]['properties']['identifier']
    return render_template('item.html', data=data, title=title)


@app.route('/<label>/<uid>', methods=['GET'])
def item(label, uid):
    ''' generic page for an item '''
    #TODO: error handling, sanitization
    logging.info('loading %s: %s', label, uid)
    data = graph.get_node(uid)
    title = '%s (%s)' % (data['nodes'][0]['properties']['identifier'],
                         (label[0].upper() + label[1:]))
    return render_template('item.html', data=data, title=title)


@app.route('/<label>', methods=['GET'])
def list(label):
    ''' list of entried for a label '''
    label = sanitize(label)
    data = graph.get_all(label)
    title = 'List of %s' % capitalize_filter(format_filter(label))
    return render_template('list.html', data=data, title=title, label=label)


# ----- filters
@app.template_filter('format')
def format_filter(rel):
    ''' cleanup _ lines '''
    return re.sub('_', ' ', rel)


@app.template_filter('capitalize')
def capitalize_filter(text):
    ''' capitalize words '''
    return text[0].upper() + text[1:]


@app.template_filter('pluralize')
def pluralize(text):
    ''' fishs '''
    if text[-1] == 'y':
        return text[:-1] + 'ies'
    elif text[-1] in ['h', 's']:
        return text + 'es'
    return text + 's'


# ----- utilities
def grimoire_date(props):
    ''' get a nicely formatted year for a grimoire '''
    if 'year' in props and props['year']:
        date = props['year']
    elif 'decade' in props and props['decade']:
        date = '%ss' % props['decade']
    elif 'century' in props and props['century']:
        try:
            cent = int(props['century'][:-2])
            date = '%dth century' % (cent + 1)
        except ValueError:
            date = '%ss' % props['century']
    else:
        date = ''

    return date

def sanitize(text, allow_spaces=False):
    ''' don't let any fuckery in to neo4j '''
    regex = r'[a-zA-z\-\d]'
    if allow_spaces:
        regex = r'[a-zA-z\-\s\d]'
    return ''.join([t.lower() for t in text if re.match(regex, t)])

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=4080)
