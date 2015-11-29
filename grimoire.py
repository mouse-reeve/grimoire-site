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


@app.route('/<label>/<uid>', methods=['GET'])
def item(label, uid):
    ''' generic page for an item '''
    label = sanitize(label)
    if not graph.validate_label(label):
        logging.error('Invalid label %s', label)
        labels = graph.get_labels()
        return render_template('label-404.html', labels=labels)

    uid = sanitize(uid)
    logging.info('loading %s: %s', label, uid)
    data = graph.get_node(uid)
    if not data['nodes']:
        logging.error('Invalid uid %s', uid)
        items = graph.get_all(label)
        return render_template('item-404.html', items=items['nodes'], label=label)

    node = data['nodes'][0]
    rels = data['relationships']

    rel_exclusions = []
    prop_exclusions = []
    template = 'item.html'

    entities = ['angel', 'demon', 'olympian_spirit', 'fairy']
    if label == 'grimoire':
        template = 'grimoire.html'
        prop_exclusions = ['year', 'decade', 'century']
        rel_exclusions = ['lists', 'has']

        data['date'] = grimoire_date(node['properties'])
        data['editions'] = [r for r in rels
                            if r['end']['label'] and r['end']['label'] == 'edition']
        data['entities'] = {}
        for entity in entities:
            data['entities'][entity] = [r for r in rels
                                        if r['end']['label'] and r['end']['label'] == entity]
    elif label == 'topic':
        template = 'topic.html'
        data['entities'] = {}
        rel_exclusions = ['teaches', 'skilled_in']
        for entity in entities:
            data['entities'][entity] = [r for r in rels
                                        if r['start']['label'] and r['start']['label'] == entity]
    elif label == 'fairy':
        # removes duplication of two-way sister relationships
        rels = [r for r in rels if r['type'] != 'has_sister' or r['end']['id'] != node['id']]

    data['relationships'] = [r for r in rels if not r['type'] in rel_exclusions]
    data['properties'] = {k:v for k, v in node['properties'].items() if not k in prop_exclusions}
    data['has_details'] = len([k for k in data['properties'].keys()
                               if not k in ['uid', 'content', 'identifier']]) > 0

    title = '%s (%s)' % (node['properties']['identifier'], capitalize_filter(format_filter(label)))
    return render_template(template, data=data, title=title, label=label)


@app.route('/<label>', methods=['GET'])
def category(label):
    ''' list of entried for a label '''
    label = sanitize(label)
    if not graph.validate_label(label):
        labels = graph.get_labels()
        return render_template('label-404.html', labels=labels)
    data = graph.get_all(label)
    title = 'List of %s' % capitalize_filter(format_filter(label))
    return render_template('list.html', data=data, title=title, label=label)


# ----- filters
@app.template_filter('format')
def format_filter(rel):
    ''' cleanup _ lines '''
    if not rel:
        return rel
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
