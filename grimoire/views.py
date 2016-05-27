''' misc views '''
import copy
from datetime import date
from email.mime.text import MIMEText
from flask import redirect, request, render_template as flask_render_template
import markdown
from subprocess import Popen, PIPE
from werkzeug.exceptions import BadRequestKeyError

import grimoire.helpers as helpers
from grimoire.helpers import render_template
from grimoire import app, graph, entities, date_params, templates


@app.before_request
def before_request():
    ''' check rendered template cache '''
    url = request.url
    if url in templates:
        return templates[url]


@app.route('/')
def index():
    ''' render the basic template for angular '''
    data = graph.get_all('grimoire')
    grimoires = []
    for g in data['nodes']:
        g = g['properties']
        year = helpers.grimoire_date(g)

        grimoires.append({
            'uid': g['uid'],
            'identifier': g['identifier'],
            'date': year
        })
        grimoires = sorted(grimoires, key=lambda grim: grim['identifier'])
    excerpt = graph.get_frontpage_random()['nodes'][0]
    excerpt['properties']['content'] = markdown.markdown(excerpt['properties']['content'])
    return flask_render_template('home.html', grimoires=grimoires,
                                 title='Grimoire Encyclopedia', excerpt=excerpt)


@app.route('/support')
def support():
    ''' the "give me money" page '''
    return render_template(request.url, 'support.html', title='Support Grimoire dot org')


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
        return redirect('/%s/%s' % (item['label'], item['properties']['uid']))
    return render_template(request.url, 'search.html', results=data['nodes'], term=term)


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
        entity_list[i]['grimoires'] = {g['properties']['uid']: g for g in grimoire_list}
        all_grimoires.append(entity_list[i]['grimoires'])

    grimoires = {}
    for d in all_grimoires:
        for key, value in d.items():
            grimoires[key] = value
    grimoires = grimoires.values()
    grimoires = sorted(grimoires, key=lambda g: g['properties']['date'])

    isolates_data = graph.get_single_grimoire_entities(entity)
    isolates = zip(isolates_data['nodes'], isolates_data['lists'])

    return render_template(request.url, 'table.html', entity=entity, grimoires=grimoires,
                           entities=entity_list, isolates=isolates, table=True)


@app.route('/spell')
def spell():
    ''' custom page for spells '''
    data = graph.get_spells_by_outcome()
    spells = {k['properties']['identifier']: v for k, v in zip(data['nodes'], data['lists'])}
    return render_template(request.url, 'spells.html', spells=spells, title='List of Spells')

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
        grimoires = graph.get_all('grimoire', with_connection_label=label)['nodes']
        if len(grimoires) < 2:
            grimoires = None

    return render_template(request.url, template, items=items,
                           title=title, label=label,
                           grimoires=grimoires, filtered=filtered)


@app.route('/compare/<uid_1>/<uid_2>')
def compare(uid_1, uid_2):
    ''' compare two items of the same type '''
    data = (helpers.get_node(uid_1), helpers.get_node(uid_2))
    nodes = [d['node'] for d in data]
    rels = [d['relationships'] for d in data]

    # ----- check that item 1 and item 2 are of the same type
    if not nodes[0]['label'] == nodes[1]['label']:
        return render_template(request.url, 'compare-failure.html',
                               title='Oops: Invalid Comparison')

    # ----- get all shared items to list out
    shared_list = {}

    # entities (demon/angel/fairy/whatever)
    for entity in entities + ['spell']:
        entity_lists = [helpers.extract_rel_list_by_type(rels[0], 'lists', 'end', label=entity),
                        helpers.extract_rel_list_by_type(rels[1], 'lists', 'end', label=entity)]
        shared_list[entity] = intersection(entity_lists[0], entity_lists[1])

    # grimoires (for spells or entities that are being compared)
    books = [helpers.extract_rel_list_by_type(rels[0], 'lists', 'start', label='parent:book'),
             helpers.extract_rel_list_by_type(rels[1], 'lists', 'start', label='parent:book')]
    shared_list['grimoire'] = intersection(books[0], books[1])

    title = '"%s" vs "%s"' % (nodes[0]['properties']['identifier'],
                              nodes[1]['properties']['identifier'])

    # ----- compare remaining relationships
    exclude = ['lists']
    rels = [helpers.exclude_rels(rel_list, exclude) for rel_list in rels]
    # make a dictionary for each relationship type with an empty array value
    # ie: {'wrote': [[], []], 'influenced': [[], []]}
    types = {t: [[], []] for t in list(set([r['type'] for r in rels[0] + rels[1]]))}

    # populate types dictionary with every relationship of that type
    for (i, rel_list) in enumerate(rels):
        for rel in rel_list:
            types[rel['type']][i] += [rel]

    # remove types that only exist for one item or the other
    types = {k:v for (k, v) in types.items() if v[0] and v[1]}

    same = []
    different = []

    for rel_type in types:
        relset = types[rel_type]
        direction = 'end' if \
                    relset[0][0]['start']['properties']['uid'] == nodes[0]['properties']['uid'] \
                    else 'start'
        subjects = [[rel[direction] for rel in r] for r in relset]
        same_uids = [i['properties']['uid'] for i in intersection(subjects[0], subjects[1])]
        same += [[rel for rel in r if rel[direction]['properties']['uid'] in same_uids] for r in relset][0]

    return render_template(request.url, 'compare.html', title=title, same=same, different=different,
                           shared_lists=shared_list, item_1=nodes[0], item_2=nodes[1],
                           default_collapse=False)


def difference(nodes_1, nodes_2):
    ''' find all the shared nodes between two lists '''
    keys = [[n['properties']['uid'] for n in nodes_1],
            [n['properties']['uid'] for n in nodes_2]]
    shared_uids = list(set(keys[0]) & set(keys[1]))
    return [n for n in nodes_1 + nodes_2 if not n['properties']['uid'] in shared_uids]


def intersection(nodes_1, nodes_2):
    ''' find all the shared nodes between two lists '''
    keys = [[n['properties']['uid'] for n in nodes_1],
            [n['properties']['uid'] for n in nodes_2]]
    shared_uids = list(set(keys[0]) & set(keys[1]))
    return [n for n in nodes_1 if n['properties']['uid'] in shared_uids]


@app.route('/feedback', methods=['POST'])
def feedback():
    ''' email out user feedback
    :return: sends user back to the page they were on '''
    referer = request.headers.get('Referer')

    message = '\n'.join([k + ': ' + v for (k, v) in request.form.items()])
    msg = MIMEText(message)
    msg['To'] = 'mouse.reeve@gmail.com'
    msg['From'] = 'feedback@grimoire.org'
    msg['Subject'] = 'Feedback: %s' % referer
    p = Popen(['/usr/sbin/sendmail', '-t', '-oi'], stdin=PIPE)
    p.communicate(msg.as_string())

    return redirect(referer)


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
    if graph.timeline_labels == []:
        graph.timeline_labels = set([n['label'] for n in nodes])

    show = [l for l in graph.timeline_labels \
            if request.args.has_key(l) and request.values[l] == 'on']

    if show:
        nodes = [n for n in nodes if n['label'] in show]
    else:
        show = graph.timeline_labels

    timeline = {}
    for node in nodes:
        for event in date_params:
            if not event in node['properties']:
                continue
            try:
                year = int(node['properties'][event])
            except ValueError:
                continue

            date_precision = node['properties']['date_precision'] \
                             if 'date_precision' in node['properties'] else 'year'
            note = event if not event in ['year', 'date'] else None

            timeline = add_to_timeline(timeline, node, year, date_precision, note=note)

    end = date.today().year
    return render_template(request.url, 'timeline.html', data=timeline, end=end,
                           labels=graph.timeline_labels, show=show)


def add_to_timeline(timeline, node, year, date_precision, note=None):
    ''' put a date on it
    :param timeline: the existing timeline object
    :param year: the year/decade/century of origin
    :param date_precision: how precide the date is (year/decade/century)
    :param node: the node
    :param note: display text to go along with the node (if available)
    :return: updated timeline object
    '''
    new_node = copy.copy(node)
    if note:
        new_node['note'] = note

    try:
        year = int(year)
    except ValueError:
        return timeline

    century = year / 100 * 100
    decade = year / 10 * 10 if date_precision != 'century' else None
    year = year if date_precision == 'year' else None

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
