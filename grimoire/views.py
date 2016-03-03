""" misc views """
import copy
from flask import redirect, render_template, request
from werkzeug.exceptions import BadRequestKeyError

import grimoire.helpers as helpers
from grimoire import app, graph, entities


@app.route('/')
def index():
    """ render the basic template for angular """
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
        grimoires = sorted(grimoires, key=lambda grim: grim['identifier'])
    return render_template('home.html', grimoires=grimoires, title='Grimoire Metadata')


@app.route('/random')
def random():
    """ pick a node, any node """
    data = graph.random()
    return redirect(data['nodes'][0]['link'])


@app.route('/index')
def content_index():
    """ list everything available by category """
    data = []
    for label in graph.get_labels():
        data.append({
            'label': label,
            'nodes': graph.get_all(label)['nodes']
        })
    return render_template('index.html', data=data, title='Index')


@app.route('/support')
def support():
    """ the "give me money" page """
    return render_template('support.html', title='Support Grimoire dot Org')


@app.route('/search')
def search():
    """ look up a term """
    try:
        term = helpers.sanitize(request.values['term'], allow_spaces=True)
    except BadRequestKeyError:
        return redirect('/')

    if not term:
        return redirect('/')
    data = graph.search(term)

    # if there's only one result, redirect
    if len(data['nodes']) == 1:
        item = data['nodes'][0]
        return redirect('/%s/%s' % (item['label'], item['properties']['uid']))
    return render_template('search.html', results=data['nodes'], term=term)


@app.route('/table')
@app.route('/table/<entity>')
def table(entity='demon'):
    """ a comparison table for grimoires and entities
    :param entity: the type of creature (default is demon)
    :return: the rendered table page
    """
    if entity not in entities:
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
    """ list of entries for a label
    :param label: the type of data to list out
    :return: rendered list page
    """
    label = helpers.sanitize(label)
    if not graph.validate_label(label):
        labels = graph.get_labels()
        return render_template('label-404.html', labels=labels)

    filtered = None
    try:
        item1 = helpers.sanitize(request.values['i'])
        item2 = helpers.sanitize(request.values['j'])
        operator = helpers.sanitize(request.values['op'])
        if operator not in ['and', 'not']:
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
        items[letter] = [node] if letter not in items else items[letter] + [node]

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


@app.route('/timeline')
def timeline_page():
    """ timeline data display
    :return: rednered timeline page
    """
    grimoires = graph.get_all('grimoire')['nodes'] + graph.get_all('book')['nodes']
    centuries = [int(t['properties']['century'])
                 if t['properties']['century'] else 0 for t in grimoires]
    end = reduce(lambda x, y: x if x > y else y, centuries)
    start = reduce(lambda x, y: x if x < y else y, centuries)
    timeline = {}

    for grim in grimoires:
        century = grim['properties']['century']
        decade = grim['properties']['decade']
        year = grim['properties']['year']
        timeline = add_to_timeline(timeline, century, grim, decade=decade, year=year)

    # people's birth/death
    people = graph.get_all('person')['nodes']
    for person in people:
        for event in ['born', 'died', 'crowned']:
            if event in person['properties']:
                year = person['properties'][event]
                decade = year - year % 10
                century = year - year % 100

                timeline = add_to_timeline(timeline, century, person, decade=decade,
                                           year=year, note=event)

    events = graph.get_all('historical_event')['nodes']
    for item in events:
        for event in ['began', 'ended']:
            if event in item['properties']:
                year = item['properties'][event]
                decade = year - year % 10
                century = year - year % 100

                timeline = add_to_timeline(timeline, century, item, decade=decade,
                                           year=year, note=event)

    # misc things with a date fields
    items = graph.get_with_param('date')['nodes']
    for item in items:
        year = item['properties']['date']
        decade = year - year % 10
        century = year - year % 100

        timeline = add_to_timeline(timeline, century, item, decade=decade,
                                   year=year)

    return render_template('timeline.html', data=timeline, start=start, end=end)


def add_to_timeline(timeline, century, node, note=None, decade=None, year=None):
    """ put a date on it
    :param timeline: the existing timeline object
    :param century: the century from which the node dates
    :param node: the node
    :param note: display text to go along with the node
    :param decade: decade of the node (if available)
    :param year: year of the node (if available)
    :return: updated timeline object
    """
    new_node = copy.copy(node)
    if note:
        new_node['note'] = note

    if century not in timeline:
        timeline[century] = {'decades': {}, 'items': []}
    if decade and decade not in timeline[century]['decades']:
        timeline[century]['decades'][decade] = {'years': {}, 'items': []}
    if year and year not in timeline[century]['decades'][decade]['years']:
        timeline[century]['decades'][decade]['years'][year] = {'items': []}

    if year:
        timeline[century]['decades'][decade]['years'][year]['items'] += [new_node]
    elif decade:
        timeline[century]['decades'][decade]['items'] += [new_node]
    else:
        timeline[century]['items'] += [new_node]

    return timeline
