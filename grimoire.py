''' webserver for grimoire graph data '''
from collections import defaultdict
from flask import Flask, redirect, render_template, request
from graph_service import GraphService
import logging
import re
from werkzeug.exceptions import BadRequestKeyError

app = Flask(__name__)
graph = GraphService()

entities = ['angel', 'demon', 'olympian_spirit', 'fairy', 'aerial_spirit']

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


@app.route('/table')
@app.route('/table/<entity>', methods=['GET'])
def table(entity='demon'):
    ''' a comparison table for grimoires and entities '''
    if not entity in entities:
        return redirect('/table')

    data = graph.get_grimoire_entities(entity)
    grimoires = data['nodes']

    all_entities = []
    for i, entity_list in enumerate(data['lists']):
        grimoires[i]['entities'] = {e['properties']['uid']: e for e in entity_list}
        all_entities.append(grimoires[i]['entities'])

    entity_list = {}

    for d in all_entities:
        for key, value in d.items():
            entity_list[key] = value

    return render_template('table.html', entity=entity, grimoires=grimoires,
                           entities=entity_list, table=True)


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
    template = 'item.html'

    if label == 'fairy':
        # removes duplication of two-way sister relationships
        rels = [r for r in rels if r['type'] != 'has_sister' or r['end']['id'] != node['id']]

    if label == 'grimoire':
        template = 'grimoire.html'
        rel_exclusions = ['lists', 'has']

        data['date'] = grimoire_date(node['properties'])
        data['editions'] = extract_rel_list(rels, 'edition', 'end')
        data['entities'] = {}
        for entity in entities:
            data['entities'][entity] = extract_rel_list(rels, entity, 'end')
    elif label == 'art':
        template = 'topic.html'
        data['entities'] = {}
        rel_exclusions = ['teaches', 'skilled_in']
        for entity in entities:
            data['entities'][entity] = extract_rel_list(rels, entity, 'start')
    elif label in entities:
        template = 'entity.html'
        rel_exclusions = ['lists', 'teaches', 'skilled_in']
        data['grimoires'] = extract_rel_list(rels, 'grimoire', 'start')
        data['skills'] = extract_rel_list(rels, 'art', 'end')

    data['relationships'] = [r for r in rels if not r['type'] in rel_exclusions]
    data['id'] = node['id']
    data['properties'] = {k:v for k, v in node['properties'].items() if
                          not k in ['year', 'decade', 'century']}
    data['has_details'] = len([k for k in data['properties'].keys()
                               if not k in ['uid', 'content', 'identifier']]) > 0

    sidebar = []
    related = graph.related(uid, label)
    # similar items of the same type
    if related['nodes']:
        sidebar = [{'title': 'Similar %s' % pluralize(capitalize_filter(label)),
                    'data': related['nodes']}]

    sidebar += get_others(data['relationships'], node)

    title = '%s (%s)' % (node['properties']['identifier'], capitalize_filter(label))

    return render_template(template, data=data, title=title, label=label, sidebar=sidebar)


def get_others(rels, node):
    '''
    other items of the node's type related to something it is related to.
    For example: "Other editions by the editor Joseph H. Peterson"
    '''
    label = node['label']
    others = []
    for rel in rels:
        start = rel['start']
        end = rel['end']

        # must be different types of data, and not entities in a grimoire
        if start['label'] != end['label'] and \
                (end['label'] != 'demon' and start['label'] != 'grimoire'):
            # other = "editions"
            other = start if start['label'] != label else end
            other_items = graph.others_of_type(label,
                                               other['properties']['uid'],
                                               node['properties']['uid'])
            if other_items['nodes']:
                others.append({
                    'title': 'Other %s related to the %s %s' %
                             (pluralize(label), format_filter(other['label']),
                              other['properties']['identifier']),
                    'data': other_items['nodes']
                })
    return others


@app.route('/<label>', methods=['GET'])
def category(label):
    ''' list of entried for a label '''
    label = sanitize(label)
    if not graph.validate_label(label):
        labels = graph.get_labels()
        return render_template('label-404.html', labels=labels)

    filtered = None
    try:
        item1 = sanitize(request.values['i'])
        item2 = sanitize(request.values['j'])
        operator = sanitize(request.values['op'])
        if not operator in ['and', 'not']:
            raise BadRequestKeyError
    except (KeyError, BadRequestKeyError):
        data = graph.get_all(label)
    else:
        data = graph.get_filtered(label, item1, item2, operator)
        filtered = {
            'operator': operator,
            'item1': graph.get_node(item1)['nodes'][0],
            'item2': graph.get_node(item2)['nodes'][0]
        }

    items = {}
    for node in data['nodes']:
        letter = node['properties']['identifier'][0].upper()
        items[letter] = [node] if not letter in items else items[letter] + [node]

    template = 'list.html'
    title = 'List of %s' % capitalize_filter(format_filter(label))

    grimoires = []
    if label in entities:
        template = 'entity-list.html'
        grimoires = graph.get_all('grimoire', with_connection_label=label)['nodes']
        if len(grimoires) < 2:
            grimoires = None

    return render_template(template, items=items,
                           title=title, label=label,
                           grimoires=grimoires, filtered=filtered)


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
    text = format_filter(text)
    return text[0].upper() + text[1:]


@app.template_filter('pluralize')
def pluralize(text):
    ''' fishs '''
    text = format_filter(text)
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


def extract_rel_list(rels, label, position):
    ''' get all relationships to a node for a given type '''
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label]

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=4080)
