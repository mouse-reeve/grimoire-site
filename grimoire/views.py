''' misc views '''
from datetime import date

from flask import redirect, request, render_template as flask_render_template
from markdown import markdown
from werkzeug.exceptions import BadRequestKeyError

import grimoire.helpers as helpers
from grimoire import app, graph, entities, date_params, templates
from grimoire.helpers import render_template


@app.before_request
def before_request():
    ''' check rendered template cache '''
    if not app.debug:
        url = request.url
        if url in templates:
            return templates[url]


@app.after_request
def after_request(response):
    ''' save rendered page '''
    from htmlmin.main import minify
    import os
    if response.content_type == u'text/html; charset=utf-8':
        # minify
        response.set_data(minify(response.get_data(as_text=True)))

        # update static dir
        rendered = open('%s/_site%s/index.html' % \
                        (os.getcwd(), request.path), 'w')
        rendered.write(response.data)
    return response


@app.route('/')
def index():
    ''' render the basic template for angular '''
    data = graph.get_all('grimoire')
    grimoires = []
    for g in data['nodes']:
        g = g['props']
        year = helpers.grimoire_date(g)

        grimoires.append({
            'uid': g['uid'],
            'identifier': g['identifier'],
            'date': year,
            'timestamp': g['date']
        })
        grimoires = sorted(grimoires, key=lambda grim: grim['timestamp'])
    excerpt = graph.get_frontpage_random()['nodes'][0]
    excerpt['props']['content'] = markdown(excerpt['props']['content'])

    # --- map
    events = graph.get_all('event')['nodes']
    events = sorted(events,
                    key=lambda k: int(k['props']['date']),
                    reverse=True)

    for event in events:
        event['props']['display_date'] = helpers.grimoire_date(event['props'])

    # --- render template
    template_data = {
        'title': 'Grimoire Encyclopedia',
        'grimoires': grimoires,
        'excerpt': excerpt,
        'events': events
    }
    return flask_render_template('home.html', **template_data)


@app.route('/map')
def temporospatial():
    ''' render the basic template for angular '''
    events = graph.get_all('event')['nodes']
    events = sorted(events,
                    key=lambda k: int(k['props']['date']),
                    reverse=True)

    for event in events:
        event['props']['display_date'] = helpers.grimoire_date(event['props'])
    template_data = {
        'title': 'Grimoire Encyclopedia',
        'events': events
    }
    return flask_render_template('map.html', **template_data)


@app.route('/support')
def support():
    ''' the "give me money" page '''
    return render_template(request.url, 'support.html',
                           title='Support Grimoire dot org')


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

    # if there's only one result, redirect
    if len(data['nodes']) == 1:
        item = data['nodes'][0]
        return redirect('/%s/%s' % (item['label'], item['props']['uid']))
    template_data = {
        'results': data['nodes'],
        'term': term
    }
    return render_template(request.url, 'search.html', **template_data)


@app.route('/table')
@app.route('/table/<entity>')
def table(entity='demon'):
    ''' a comparison table for grimoires and entities
    :param entity: the type of creature (default is demon)
    :return: the rendered table page
    '''
    if entity not in entities + ['spell']:
        return redirect('/table')

    data = graph.get_grimoire_entities(entity)
    entity_list = data['nodes']

    all_grimoires = []
    for i, grimoire_list in enumerate(data['lists']):
        entity_list[i]['grimoires'] = \
                {g['props']['uid']: g for g in grimoire_list}
        all_grimoires.append(entity_list[i]['grimoires'])

    grimoires = {}
    for d in all_grimoires:
        for key, value in d.items():
            grimoires[key] = value
    grimoires = grimoires.values()
    grimoires = sorted(grimoires, key=lambda g: g['props']['date'])

    isolates_data = graph.get_single_grimoire_entities(entity)
    isolates = zip(isolates_data['nodes'], isolates_data['lists'])

    return render_template(request.url, 'table.html', entity=entity,
                           grimoires=grimoires, entities=entity_list,
                           isolates=isolates, table=True)


@app.route('/spell')
def spell():
    ''' custom page for spells
    :return: rendered spell page template '''
    sort = 'outcome'
    try:
        sort = helpers.sanitize(request.values['sort'], allow_spaces=True)
    except BadRequestKeyError:
        pass

    if sort == 'outcome':
        data = graph.get_spells_by_outcome()
    elif sort == 'grimoire':
        data = graph.get_spells_by_grimoire()
    else:
        return redirect('/spell')

    spells = {k['props']['identifier']: v
              for k, v in zip(data['nodes'], data['lists'])}
    return render_template(request.url, 'spells.html',
                           spells=spells, sort=sort,
                           title='List of Spells')


@app.route('/<label>')
def category(label):
    ''' list of entries for a label
    :param label: the type of data to list out
    :return: rendered list page
    '''
    label = helpers.sanitize(label)
    if not graph.validate_label(label):
        labels = graph.get_labels()
        return render_template(request.url, 'label-404.html', labels=labels)

    filtered = None
    try:
        item1 = helpers.sanitize(request.values['i'])
    except KeyError:
        data = graph.get_all(label)
    else:
        try:
            item2 = helpers.sanitize(request.values['j'])
            operator = helpers.sanitize(request.values['op'])
            if operator not in ['and', 'not']:
                raise BadRequestKeyError
        except (KeyError, BadRequestKeyError):
            data = graph.get_filtered(label, item1)
            filtered = {
                'item1': graph.get_node(item1)['nodes'][0],
            }
        else:
            data = graph.get_filtered(label, item1, item2, operator)
            filtered = {
                'operator': operator,
                'item1': graph.get_node(item1)['nodes'][0],
                'item2': graph.get_node(item2)['nodes'][0]
            }

    items = data['nodes']

    template = 'list.html'
    title = 'List of %s' % helpers.capitalize_filter(helpers.pluralize(label))

    grimoires = []
    if label in entities:
        template = 'entity-list.html'
        grimoires = graph.get_all('grimoire',
                                  with_connection_label=label)['nodes']
        if len(grimoires) < 2:
            grimoires = None

    return render_template(request.url, template, items=items,
                           title=title, label=label,
                           grimoires=grimoires, filtered=filtered)


@app.route('/updates')
def updates():
    ''' Simple page of updates I've posted '''
    return render_template(request.url, 'updates.html', title='News & Updates')


@app.route('/timeline')
def timeline_page():
    ''' timeline data display
    :return: rendered timeline page
    '''

    nodes = graph.timeline()['nodes']
    if not graph.timeline_labels:
        graph.timeline_labels = set([n['label'] for n in nodes])

    show = [l for l in graph.timeline_labels
            if l in request.args and request.values[l] == 'on']

    if show:
        nodes = [n for n in nodes if n['label'] in show]
    else:
        show = graph.timeline_labels

    timeline = {}
    for node in nodes:
        for event in date_params:
            if event not in node['props']:
                continue
            try:
                year = int(node['props'][event])
            except ValueError:
                continue

            date_precision = node['props'].get('date_precision', 'year')

            note = event if event not in ['year', 'date'] else None
            timeline = helpers.add_to_timeline(timeline, node, year,
                                               date_precision, note=note)

    end = date.today().year
    return render_template(request.url, 'timeline.html', data=timeline, end=end,
                           labels=graph.timeline_labels, show=show)
