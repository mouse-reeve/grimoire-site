''' webserver for grimoire graph data '''
from flask import Flask, redirect, render_template, request
from graph_service import GraphService
import helpers
import logging
import re
from werkzeug.exceptions import BadRequestKeyError

app = Flask(__name__)
graph = GraphService()

entities = ['angel', 'demon', 'olympian_spirit', 'fairy', 'aerial_spirit']

# ----- routes
@app.route('/')
def index():
    ''' render the basic template for angular '''
    data = graph.get_all('grimoire')
    grimoires = []
    for g in data['nodes']:
        g = g['properties']
        date = helpers.grimoire_date(g)

        grimoires.append({
            'uid': g['uid'],
            'identifier': g['identifier'],
            'date': date
        })
        grimoires = sorted(grimoires, key=lambda g: g['identifier'])
    return render_template('home.html', grimoires=grimoires, title='Grimoire Metadata')


@app.route('/random')
def random():
    ''' pick a node, any node '''
    data = graph.random()
    return redirect(data['nodes'][0]['link'])


@app.route('/index')
def content_index():
    ''' list everything available by category '''
    data = []
    for label in graph.get_labels():
        data.append({
            'label': label,
            'nodes': graph.get_all(label)['nodes']
        })
    return render_template('index.html', data=data, title='Index')


@app.route('/support')
def support():
    ''' the "give me money" page '''
    return render_template('support.html')


@app.route('/search')
def search():
    ''' look up a term '''
    try:
        term = helpers.sanitize(request.values['term'], allow_spaces=True)
    except BadRequestKeyError:
        return redirect('/')
    data = graph.search(term)
    return render_template('search.html', results=data['nodes'], term=term)


@app.route('/table')
@app.route('/table/<entity>')
def table(entity='demon'):
    ''' a comparison table for grimoires and entities '''
    if not entity in entities:
        return redirect('/table')

    data = graph.get_grimoire_entities(entity)
    entity_list = data['nodes']

    all_grimoires = []
    for i, grimoire_list in enumerate(data['lists']):
        entity_list[i]['grimoires'] = {e['properties']['uid']: e for e in grimoire_list}
        all_grimoires.append(entity_list[i]['grimoires'])

    grimoires = {}

    for d in all_grimoires:
        for key, value in d.items():
            grimoires[key] = value

    isolates_data = graph.get_single_grimoire_entities(entity)
    isolates = zip(isolates_data['nodes'], isolates_data['lists'])

    return render_template('table.html', entity=entity, grimoires=grimoires,
                           entities=entity_list, isolates=isolates, table=True)


@app.route('/<label>/<uid>')
def item(label, uid):
    ''' generic page for an item '''
    label = helpers.sanitize(label)
    if not graph.validate_label(label):
        logging.error('Invalid label %s', label)
        return render_template('label-404.html', labels=graph.get_labels())

    uid = helpers.sanitize(uid)
    logging.info('loading %s: %s', label, uid)
    data = graph.get_node(uid)
    if not data['nodes']:
        logging.error('Invalid uid %s', uid)
        items = graph.get_all(label)
        return render_template('item-404.html', items=items['nodes'],
                               search=graph.search(uid)['nodes'], label=label)

    node = data['nodes'][0]
    rels = data['relationships']

    rel_exclusions = []
    template = 'item.html'

    if label == 'fairy':
        # removes duplication of two-way sister relationships
        rels = [r for r in rels if r['type'] != 'is_a_sister_of' or r['end']['id'] != node['id']]

    if label == 'grimoire':
        template = 'grimoire.html'
        rel_exclusions = ['lists', 'has', 'includes']
        data = grimoire_item(data, node, rels)

    elif label == 'art':
        template = 'topic.html'
        data['entities'] = {}
        rel_exclusions = ['teaches', 'skilled_in']
        for entity in entities:
            data['entities'][entity] = helpers.extract_rel_list(rels, entity, 'start')
    elif label in entities:
        template = 'entity.html'
        data = entity_item(data, node, rels)
        rel_exclusions = ['lists', 'teaches', 'skilled_in', 'serves']
    elif label == 'language':
        template = 'language.html'
        rel_exclusions = ['was_written_in']
        data['grimoires'] = helpers.extract_rel_list(rels, 'grimoire', 'start')
    elif label == 'edition':
        template = 'edition.html'
        rel_exclusions = ['published', 'edited', 'has']
        data['publisher'] = helpers.extract_rel_list(rels, 'publisher', 'start')
        data['editors'] = helpers.extract_rel_list(rels, 'editor', 'start')
        data['grimoire'] = helpers.extract_rel_list(rels, 'grimoire', 'start')[0]

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


def grimoire_item(data, node, rels):
    ''' format data for grimoires '''
    data['date'] = helpers.grimoire_date(node['properties'])
    data['editions'] = helpers.extract_rel_list(rels, 'edition', 'end')
    data['spells'] = helpers.extract_rel_list(rels, 'spell', 'end')
    data['entities'] = {}
    for entity in entities:
        data['entities'][entity] = helpers.extract_rel_list_by_type(rels, 'lists', entity, 'end')

    return data


def entity_item(data, node, rels):
    ''' format data for entities '''
    data['grimoires'] = helpers.extract_rel_list(rels, 'grimoire', 'start')
    data['skills'] = helpers.extract_rel_list(rels, 'art', 'end')
    data['serves'] = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'end')
    data['serves'] = [s for s in data['serves'] if
                      not s['properties']['uid'] == node['properties']['uid']]
    data['servants'] = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'start')
    data['servants'] = [s for s in data['servants'] if
                        not s['properties']['uid'] == node['properties']['uid']]
    return data


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


@app.route('/<label>')
def category(label):
    ''' list of entried for a label '''
    label = helpers.sanitize(label)
    if not graph.validate_label(label):
        labels = graph.get_labels()
        return render_template('label-404.html', labels=labels)

    filtered = None
    try:
        item1 = helpers.sanitize(request.values['i'])
        item2 = helpers.sanitize(request.values['j'])
        operator = helpers.sanitize(request.values['op'])
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
    if text == 'person':
        return 'people'
    if text[-1] == 'y':
        return text[:-1] + 'ies'
    elif text[-1] in ['h', 's']:
        return text + 'es'
    return text + 's'


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=4080)
