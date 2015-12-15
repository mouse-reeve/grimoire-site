''' misc views '''
from flask import redirect, render_template, request
from werkzeug.exceptions import BadRequestKeyError

from grimoire import app, graph, entities
import grimoire.helpers as helpers

entities = ['angel', 'demon', 'olympian_spirit', 'fairy', 'aerial_spirit']


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

    if not term:
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
    title = 'List of %s' % helpers.capitalize_filter(label)

    grimoires = []
    if label in entities:
        template = 'entity-list.html'
        grimoires = graph.get_all('grimoire', with_connection_label=label)['nodes']
        if len(grimoires) < 2:
            grimoires = None

    return render_template(template, items=items,
                           title=title, label=label,
                           grimoires=grimoires, filtered=filtered)
