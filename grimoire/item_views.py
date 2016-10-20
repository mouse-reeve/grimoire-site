''' views for the item type pages '''
import logging

from flask import redirect, request
from markdown import markdown

import grimoire.helpers as helpers
from grimoire.helpers import extract_rel_list, extract_rel_list_by_type
from grimoire.helpers import render_template
from grimoire import app, graph, entities


@app.route('/event/<uid>')
@app.route('/excerpt/<uid>')
def redirect_excerpts(uid):
    ''' Re-route anyone who lands on an excerpt page to the proper node
    :param uid: the excerpt's identifier
    :return: a redirect to the linked content node
    '''

    data = graph.get_node(uid)
    source = extract_rel_list_by_type(data['rels'], 'event', 'start')
    if not source:
        source = extract_rel_list_by_type(data['rels'], 'excerpt', 'start')
    try:
        source = source[0]
    except IndexError:
        return render_template(request.url, 'label-404.html',
                               labels=graph.get_labels())

    return redirect(source['link'])


@app.route('/<label>/<uid>')
def item(label, uid):
    ''' generic page for an item
    :param label: the desired neo4j label
    :param uid: the human-readable uid of the node
    :return: customized data for this label rendered item page template
    '''

    # load and validate url data
    label = helpers.sanitize(label)
    if not graph.validate_label(label):
        logging.error('Invalid label %s', label)
        return render_template(request.url,
                               'label-404.html',
                               labels=graph.get_labels())

    try:
        data = helpers.get_node(uid)
    except NameError:
        items = graph.get_all(label)
        return render_template(request.url, 'item-404.html',
                               items=items['nodes'],
                               search=graph.search(uid)['nodes'],
                               label=label)

    node = data['node']
    rels = data['rels']

    # ----- page header/metadata
    title = node['props']['identifier']

    # ----- formatted data
    switch = {
        'parent:book': grimoire_item,
        'parent:entity': entity_item,
        'art': art_item,
        'language': language_item,
        'edition': edition_item,
        'publisher': publisher_item,
        'editor': editor_item,
        'default': generic_item,
        'spell': spell_item,
        'talisman': spell_item,
        'parent:ingredient': ingredient_item,
        'outcome': outcome_item
    }

    key = node['parent_label'] if node['parent_label'] in switch else \
          (label if label in switch else 'default')
    item_data = switch[key](node, rels)

    item_data['rels'] = helpers.combine_rels(item_data['rels'])

    # ----- sidebar
    sidebar = []
    related = graph.related(uid, label)
    if related['nodes']:
        sidebar = [{'title': 'Similar %s' % \
                    helpers.capitalize_filter(helpers.pluralize(label)),
                    'data': related['nodes']}]
    sidebar += get_others(data['rels'], node)

    if not item_data['content'] and not item_data['excerpts']:
        item_data['content'] = 'The %s "%s."' % \
                               (helpers.format_filter(label),
                                helpers.unthe(title))

    max_main_length = max([len(i['data']) for i in item_data['main']] + [0])
    default_collapse = len(item_data['main']) > 2 or max_main_length > 30

    return render_template(request.url, 'item.html',
                           data=item_data,
                           title=title,
                           label=label,
                           sidebar=sidebar,
                           default_collapse=default_collapse)


def generic_item(node, rels):
    ''' standard item processing
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    def format_field(field):
        ''' deal with array data '''
        if isinstance(field, list):
            return [{'text': i} for i in field]
        return [{'text': field}]

    data = {'id': node['id']}

    try:
        data['content'] = markdown(node['props']['content'])
    except AttributeError:
        data['content'] = ''

    # -- build timeline
    events = extract_rel_list(rels, 'event', 'end')
    for event in events:
        event['props']['relevant'] = True
    related = graph.get_related_events(node['props']['uid'])
    related = zip(related['nodes'], related['rels'])
    for rel_item in related:
        event = rel_item[0]
        this = 'this %s' % helpers.format_filter(node['label'])
        rel_type = helpers.format_filter(rel_item[1]['type'])
        if rel_item[1]['start']['props']['uid'] == node['props']['uid']:
            note = '(%s %s %s)' % \
                   (this, rel_type,
                    helpers.unthe(rel_item[1]['end']['props']['identifier']))
        else:
            note = '(%s %s)' % (rel_type, this)
        event['note'] = note
        events.append(event)
    data['timeline'], data['start_date'], \
            data['end_date'] = build_timeline(events)

    excerpts = extract_rel_list(rels, 'excerpt', 'end')
    for excerpt in excerpts:
        try:
            excerpt['props']['content'] = markdown(excerpt['props']['content'])
        except AttributeError:
            pass
    data['excerpts'] = excerpts

    data['images'] = extract_rel_list_by_type(rels, 'image',
                                              'end', label='image')

    # remove special node types from relationship lists
    remove = ['excerpt', 'event', 'image', 'contains_illustration']
    data['rels'] = helpers.exclude_rels(rels, remove)

    data['details'] = {k: format_field(node['props'][k]) for k in
                       node['props'] if k not in
                       ['content', 'uid', 'identifier', 'owned',
                        'buy', 'date_precision']}

    data['buy'] = node['props']['buy'] if 'buy' in node['props'] else None

    data['props'] = node['props']
    data['sidebar'] = []
    data['main'] = []
    data['has_details'] = len([d for d in data['details'] if \
                              data['details'][d]]) > 0
    data['link'] = node['link']

    return data


def grimoire_item(node, rels):
    ''' grimoire item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    data['rels'] = helpers.exclude_rels(data['rels'], [
        'lists', 'has', 'includes', 'wrote', 'was_written_in'])

    data['details']['date'] = [{'text': helpers.grimoire_date(node['props'])}]

    authors = extract_rel_list_by_type(rels, 'wrote', 'start')
    authors = extract_details(authors)
    if authors:
        data['details']['author'] = authors

    languages = extract_rel_list_by_type(rels, 'was_written_in', 'end')
    if languages:
        data['details']['language'] = extract_details(languages)

    editions = extract_rel_list(rels, 'edition', 'end')
    if editions:
        data['sidebar'].append({
            'title': 'Editions',
            'data': editions
        })

    for entity in entities:
        items = extract_rel_list_by_type(rels, 'lists', 'end', label=entity)
        if len(items):
            item_json = {
                'title': helpers.pluralize(entity),
                'data': items,
                'many': True,
                'compare': get_comparison(node, entity)
            }
            data['main'].append(item_json)

    spells = extract_rel_list(rels, 'spell', 'end')
    if len(spells):
        data['main'].append({
            'title': 'Spells',
            'data': spells,
            'many': False,
            'compare': get_comparison(node, 'spell')
        })

    talisman = extract_rel_list(rels, 'talisman', 'end')
    if len(talisman):
        data['main'].append({
            'title': 'Talismans',
            'data': talisman,
            'many': False
        })
    return data


def get_comparison(node, label):
    ''' format comparison data for a node '''
    data = []
    grim_compare = graph.get_comparisons(node['props']['uid'], label)
    for grim in zip(grim_compare['nodes'], grim_compare['lists']):
        data.append({
            'count': len(grim[1]),
            'grimoire': grim[0],
            'link': '/compare/%s/%s' % (node['props']['uid'],
                                        grim[0]['props']['uid'])
        })
    return data


def entity_item(node, rels):
    ''' entity item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    # removes duplication of two-way sister rels
    rels = [r for r in rels if r['type'] != 'is_a_sister_of' \
            or r['end']['id'] != node['id']]

    data['rels'] = helpers.exclude_rels(data['rels'], [
        'lists', 'teaches', 'skilled_in', 'serves', 'facilitates',
        'appears_like', 'can', 'for'])
    grimoires = extract_rel_list(rels, 'grimoire', 'start') + \
                extract_rel_list(rels, 'book', 'start')
    if grimoires:
        data['sidebar'].append({'title': 'Grimoires', 'data': grimoires})

    outcomes = extract_rel_list_by_type(rels, 'for', 'end')
    if outcomes:
        data['main'].append({'title': 'Powers', 'data': outcomes})

    appearance = extract_rel_list(rels, 'creature', 'end')
    if appearance:
        data['main'].append({
            'title': 'Appearance',
            'data': appearance, 'many': True})

    serves = extract_rel_list_by_type(rels, 'serves', 'end')
    serves = [s for s in serves if
              not s['props']['uid'] == node['props']['uid']]
    if serves:
        data['main'].append({'title': 'Serves', 'data': serves})

    servants = extract_rel_list_by_type(rels, 'serves', 'start')
    servants = [s for s in servants if
                not s['props']['uid'] == node['props']['uid']]
    if servants:
        data['main'].append({'title': 'Servants', 'data': servants})

    if not data['content']:
        content = 'The %s %s appears in %s' % \
                  (helpers.format_filter(node['label']),
                   node['props']['identifier'],
                   format_list(grimoires))
        data['content'] = markdown(content)
    return data


def art_item(node, rels):
    ''' art/topic item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['entities'] = {}
    for entity in entities:
        items = extract_rel_list(rels, entity, 'start')
        if len(items):
            data['main'].append({
                'title': helpers.pluralize(entity),
                'data': items,
                'many': True
            })
    data['rels'] = helpers.exclude_rels(data['rels'], ['teaches', 'skilled_in'])
    return data


def language_item(node, rels):
    ''' language item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['rels'] = helpers.exclude_rels(data['rels'], ['was_written_in'])
    grimoires = extract_rel_list(rels, 'grimoire', 'start')
    data['main'].append({
        'title': 'Grimoires Written in this Langage',
        'data': grimoires
    })
    return data


def edition_item(node, rels):
    ''' edition of a grimoire item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['rels'] = helpers.exclude_rels(data['rels'],
                                        ['published', 'edited', 'has'])
    publisher = extract_rel_list(rels, 'publisher', 'start')
    if publisher:
        data['details']['publisher'] = extract_details(publisher)

    editors = extract_rel_list(rels, 'editor', 'start')
    if editors:
        data['details']['editor'] = extract_details(editors)

    grimoire = extract_rel_list(rels, 'grimoire', 'start')
    if grimoire:
        data['details']['grimoire'] = extract_details(grimoire)

    book = extract_rel_list(rels, 'book', 'start')
    if book:
        data['details']['book'] = extract_details(book)

    return data


def publisher_item(node, rels):
    ''' publisher item page
    :param node: the publisher item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['rels'] = helpers.exclude_rels(data['rels'], ['published'])
    books = extract_rel_list(rels, 'edition', 'end')
    if books:
        data['main'].append({'title': 'Books', 'data': books})
    return data


def editor_item(node, rels):
    ''' editor of a grimoire item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['rels'] = helpers.exclude_rels(data['rels'], ['edited'])
    editions = extract_rel_list(rels, 'edition', 'end')
    if editions:
        data['main'].append({'title': 'Editions', 'data': editions})
    return data


def spell_item(node, rels):
    ''' spell item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['rels'] = helpers.exclude_rels(data['rels'], ['for', 'uses'])
    try:
        del data['details']['grimoire']
    except KeyError:
        pass

    grimoires = extract_rel_list(rels, 'grimoire', 'start') + \
                extract_rel_list(rels, 'book', 'start')
    if grimoires:
        data['sidebar'].append({'title': 'Grimoires', 'data': grimoires})
        if len(grimoires) == 1:
            data['parent_label'] = grimoires[0]

    ingredients = extract_rel_list(rels, 'parent:ingredient', 'end')
    if ingredients:
        data['main'].append({'title': 'Ingredients', 'data': ingredients})

    outcomes = extract_rel_list_by_type(rels, 'for', 'end')
    if outcomes:
        data['details']['Outcome'] = extract_details(outcomes)

    if not data['content'] and not data['excerpts']:
        content = 'This %s appears in %s, ' \
                  'and you can find the full text there. ' % \
                  (node['label'], format_list(grimoires))
        if outcomes:
            content += 'It is used for %s' % \
                       format_list(outcomes, italics=False).lower()
            if ingredients:
                content += ' and calls for %s' % \
                           format_list(ingredients, italics=False,
                                       show_label=False).lower()
            content += '. '

        data['content'] = markdown(content)
    return data


def ingredient_item(node, rels):
    ''' ingredient item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    spells = extract_rel_list(rels, 'spell', 'start') + \
             extract_rel_list(rels, 'talisman', 'start')
    if spells:
        data['main'].append({'title': 'Spells', 'data': spells})

    for entity in entities:
        items = extract_rel_list(rels, entity, 'start')
        if items:
            data['main'].append({'title': helpers.pluralize(entity),
                                 'data': items})

    data['rels'] = helpers.exclude_rels(data['rels'], ['uses'])

    return data


def outcome_item(node, rels):
    ''' spell item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    spells = extract_rel_list(rels, 'spell', 'start')
    if spells:
        data['main'].append({'title': 'Spells', 'data': spells})

    for entity in entities:
        items = extract_rel_list(rels, entity, 'start')
        if items:
            data['main'].append({'title': helpers.pluralize(entity),
                                 'data': items})

    data['rels'] = helpers.exclude_rels(data['rels'], ['for'])

    return data


@app.route('/compare')
def compare_start():
    ''' load form for comparing grimoires '''
    grimoires = graph.get_all('grimoire')['nodes']
    return render_template(request.url, 'compare.html', grimoires=grimoires)


@app.route('/compare', methods=['POST'])
def run_comparison():
    ''' redirect a comparison request
    :return: redirect to comparison page
    '''

    try:
        item1 = helpers.sanitize(request.values['grim1'])
        item2 = helpers.sanitize(request.values['grim2'])
    except KeyError:
        return redirect('/compare')
    return redirect('/compare/%s/%s' % (item1, item2))


@app.route('/compare/<uid_1>/<uid_2>')
def compare_grimoires(uid_1, uid_2):
    ''' compare two items of the same type '''
    try:
        data = (helpers.get_node(uid_1), helpers.get_node(uid_2))
    except NameError:
        return redirect('/compare')

    nodes = [d['node'] for d in data]
    rels = [d['rels'] for d in data]

    data = {
        'item_1': nodes[0],
        'item_2': nodes[1]
    }

    # ----- check that item 1 and item 2 are both grimoires
    if nodes[0]['label'] != 'grimoire' or nodes[0]['label'] != 'grimoire':
        return render_template(request.url, 'compare-failure.html',
                               title='Oops: Invalid Comparison')

    # ----- get all shared items to list out
    max_list_size = 0
    # keeps track of the biggest list
    data['shared_list'] = {}
    for entity in entities + ['spell']:
        entity_lists = [
            extract_rel_list_by_type(rel_list, 'lists', 'end', label=entity)
            for rel_list in rels]
        data['shared_list'][entity] = intersection(entity_lists[0],
                                                   entity_lists[1])
        max_list_size = max_list_size \
                        if len(data['shared_list'][entity]) < max_list_size \
                        else len(data['shared_list'][entity])
    data['default_collapse'] = max_list_size > 20

    data['title'] = '"%s" vs "%s"' % (nodes[0]['props']['identifier'],
                                      nodes[1]['props']['identifier'])

    # ----- Properties table
    grim_items = [grimoire_item(nodes[i], rels[i]) for i in range(2)]
    details = [g['details'] for g in grim_items]
    for d in details:
        d['author'] = d.get('author', [{'text': 'Unknown'}])
    keys = list(set(details[0].keys()) & set(details[1].keys()))
    keys = [k for k in keys if k not in ['Name', 'online_edition']]
    data['props'] = {k: [details[0][k], details[1][k]] for k in keys}

    # ----- compare remaining rels
    rels = [helpers.exclude_rels(rel_list, ['lists']) for rel_list in rels]

    # pull out rels between the two grimoires
    data['self_rels'] = []
    for rel in rels[0]:
        if rel['start']['props']['uid'] in [uid_1, uid_2] and \
           rel['end']['props']['uid'] in [uid_1, uid_2]:
            data['self_rels'].append(rel)

    exclude_ids = [r['id'] for r in data['self_rels']]
    rels[0] = [r for r in rels[0] if not r['id'] in exclude_ids]
    rels[1] = [r for r in rels[1] if not r['id'] in exclude_ids]

    # make a dictionary for each relationship type with an empty array value
    # ie: {'wrote': [[], []], 'influenced': [[], []]}
    types = {t: [[], []] for t in \
             list(set([r['type'] for r in rels[0] + rels[1]]))}

    # populate types dictionary with every relationship of that type
    for (i, rel_list) in enumerate(rels):
        for rel in rel_list:
            types[rel['type']][i] += [rel]

    # remove types that only exist for one item or the other
    types = {k: v for (k, v) in types.items() if v[0] and v[1]}

    data['same'] = {'start': [], 'end': []}
    for rel_type in types:
        relset = types[rel_type]
        direction = 'end' if \
                    relset[0][0]['start']['props']['uid'] == uid_1 \
                    else 'start'

        subjects = [[rel[direction] for rel in r] for r in relset]
        same_uids = [
            i['props']['uid'] for i in intersection(subjects[0], subjects[1])
        ]
        same_rels = [rel for rel in relset[0] if \
                     rel[direction]['props']['uid'] in same_uids]

        data['same']['start' if direction == 'end' else 'end'] += same_rels

    data['same'] = {
        'start': helpers.combine_rels(data['same']['start']),
        'end': helpers.combine_rels(data['same']['end'])
    }

    data['grimoires'] = graph.get_all('grimoire')['nodes']

    return render_template(request.url, 'compare.html', **data)


def get_others(rels, node):
    ''' other items of the node's type related to something it is related to.
    For example: "Other editions by the editor Joseph H. Peterson"
    :param rels: default relationship list
    :param node: the item node
    :return: customized data for this label
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
                                               other['props']['uid'],
                                               node['props']['uid'])
            if other_items['nodes']:
                others.append({
                    'title': 'Other %s related to the %s %s' %
                             (helpers.pluralize(label),
                              helpers.format_filter(other['label']),
                              other['props']['identifier']),
                    'data': other_items['nodes']
                })
    return others


def extract_details(items):
    ''' format the details object
    :param items: the extracted rel list for the category
    :return: array in the format:
    [{'text': 'John Constantine', 'link': '/person/constantine'}]
    '''
    return [{'text': i['props']['identifier'], 'link': i['link']}
            for i in items]


def format_list(nodes, italics=True, show_label=True):
    ''' add "and" and commas to a list '''
    items = [helpers.unthe(n['props']['identifier']) for n in nodes]
    if len(items) == 2:
        if italics:
            result = '_%s_ and _%s_' % (items[0], items[1])
        else:
            result = '%s and %s' % (items[0], items[1])
    elif len(items) > 1:
        if italics:
            result = '_%s_, and _%s_' % ('_, _'.join(items[0:-1]), items[-1])
        else:
            result = '%s, and %s' % (', '.join(items[0:-1]), items[-1])
    else:
        result = '_%s_' % items[0] if italics else '%s' % items[0]

    label = helpers.pluralize(nodes[0]['label']) \
            if len(items) > 1 else nodes[0]['label']

    return 'the %s %s' % (label, result) if show_label else result


def difference(nodes_1, nodes_2):
    ''' find all the shared nodes between two lists '''
    keys = [[n['props']['uid'] for n in nodes_1],
            [n['props']['uid'] for n in nodes_2]]
    shared_uids = list(set(keys[0]) & set(keys[1]))
    return [n for n in nodes_1 + nodes_2 \
            if not n['props']['uid'] in shared_uids]


def intersection(nodes_1, nodes_2):
    ''' find all the shared nodes between two lists '''
    keys = [[n['props']['uid'] for n in nodes_1],
            [n['props']['uid'] for n in nodes_2]]
    shared_uids = list(set(keys[0]) & set(keys[1]))
    return [n for n in nodes_1 if n['props']['uid'] in shared_uids]


def build_timeline(events):
    ''' helper function for item page timelines '''
    timeline = {}
    timeline_min = 0
    timeline_max = 0
    if events:
        try:
            dates = [int(e['props']['date']) for e in events]
        except ValueError:
            logging.error('Failed to parse event dates')
        else:
            events_start = min(dates)
            events_end = max(dates)

            offset = 10  # +/- some number of years
            timeline_min = (events_start - offset) / 100 * 100
            timeline_max = (events_end + offset) / 100 * 100

            for event in events:
                note = event['note'] if 'note' in event else None
                timeline = helpers.add_to_timeline(
                    timeline, event,
                    event['props']['date'],
                    event['props']['date_precision'],
                    note=note,
                    allow_events=True)
    return timeline, timeline_min, timeline_max
