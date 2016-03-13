''' views for the item type pages '''
import logging

from flask import render_template
import markdown

import grimoire.helpers as helpers
from grimoire import app, graph, entities


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
        return render_template('label-404.html', labels=graph.get_labels())

    uid = helpers.sanitize(uid)
    logging.info('loading %s: %s', label, uid)
    data = graph.get_node(uid)
    if 'nodes' not in data or not data['nodes']:
        logging.error('Invalid uid %s', uid)
        items = graph.get_all(label)
        return render_template('item-404.html', items=items['nodes'],
                               search=graph.search(uid)['nodes'], label=label)

    node = data['nodes'][0]
    rels = data['relationships']

    # ----- page header/metadata
    title = node['properties']['identifier']

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
        'spell': spell_item
    }

    key = node['parent_label'] if node['parent_label'] in switch else \
          (label if label in switch else 'default')
    item_data = switch[key](node, rels)

    # ----- sidebar
    sidebar = []
    related = graph.related(uid, label)
    if related['nodes']:
        sidebar = [{'title': 'Similar %s' % helpers.capitalize_filter(helpers.pluralize(label)),
                    'data': related['nodes']}]
    sidebar += get_others(data['relationships'], node)

    if not item_data['content']:
        item_data['content'] = 'The %s %s.' % (helpers.format_filter(label), helpers.unthe(title))

    return render_template('item.html',
                           data=item_data,
                           title=title,
                           label=label,
                           sidebar=sidebar)


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

    try:
        content = markdown.markdown(node['properties']['content'])
    except AttributeError:
        content = ''
    details = {k: format_field(node['properties'][k]) for k in node['properties'] if
               k not in ['content', 'uid', 'identifier', 'year',
                         'decade', 'century', 'owned', 'buy']}
    details['Name'] = [{'text': node['properties']['identifier']}]

    buy = node['properties']['buy'] if 'buy' in node['properties'] else None

    return {
        'id': node['id'],
        'content': content,
        'details': details,
        'properties': node['properties'],
        'relationships': rels,
        'buy': buy,
        'sidebar': [],
        'main': [],
        'has_details': len([d for d in details if details[d]]) > 0
    }


def grimoire_item(node, rels):
    ''' grimoire item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    data['relationships'] = exclude_rels(rels, [
        'lists', 'has', 'includes', 'wrote', 'was_written_in'])

    data['details']['date'] = [{'text': helpers.grimoire_date(node['properties'])}]

    authors = helpers.extract_rel_list_by_type(rels, 'wrote', 'person', 'start')
    authors = extract_details(authors)
    if authors:
        data['details']['author'] = authors

    languages = helpers.extract_rel_list_by_type(rels, 'was_written_in', 'language', 'end')
    if languages:
        data['details']['language'] = extract_details(languages)

    editions = helpers.extract_rel_list(rels, 'edition', 'end')
    if editions:
        data['sidebar'].append({
            'title': 'Editions',
            'data': editions
        })

    for entity in entities:
        items = helpers.extract_rel_list_by_type(rels, 'lists', entity, 'end')
        if len(items):
            data['main'].append({
                'title': helpers.pluralize(entity),
                'data': items,
                'many': True
            })

    spells = helpers.extract_rel_list(rels, 'spell', 'end')
    if len(spells):
        data['main'].append({
            'title': 'Spells',
            'data': spells,
            'many': False
        })
    return data


def entity_item(node, rels):
    ''' entity item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)

    # removes duplication of two-way sister relationships
    rels = [r for r in rels if r['type'] != 'is_a_sister_of' or r['end']['id'] != node['id']]

    data['relationships'] = exclude_rels(rels, [
        'lists', 'teaches', 'skilled_in', 'serves', 'facilitates', 'appears_like'])
    grimoires = helpers.extract_rel_list(rels, 'grimoire', 'start') + \
                helpers.extract_rel_list(rels, 'book', 'start')
    if grimoires:
        data['sidebar'].append({'title': 'Grimoires', 'data': grimoires})

    skills = helpers.extract_rel_list(rels, 'art', 'end') + \
             helpers.extract_rel_list(rels, 'outcome', 'end')
    if skills:
        data['main'].append({'title': 'Skills', 'data': skills, 'many': True})

    appearance = helpers.extract_rel_list(rels, 'creature', 'end')
    if appearance:
        data['main'].append({'title': 'Appearance', 'data': appearance, 'many': True})

    serves = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'end')
    serves = [s for s in serves if
              not s['properties']['uid'] == node['properties']['uid']]
    if serves:
        data['main'].append({'title': 'Serves', 'data': serves})

    servants = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'start')
    servants = [s for s in servants if
                not s['properties']['uid'] == node['properties']['uid']]
    if servants:
        data['main'].append({'title': 'Servants', 'data': servants})
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
        items = helpers.extract_rel_list(rels, entity, 'start')
        if len(items):
            data['main'].append({
                'title': helpers.pluralize(entity),
                'data': items,
                'many': True
            })
    data['relationships'] = exclude_rels(rels, ['teaches', 'skilled_in'])
    return data


def language_item(node, rels):
    ''' language item page
    :param node: the item node
    :param rels: default relationship list
    :return: customized data for this label
    '''
    data = generic_item(node, rels)
    data['relationships'] = exclude_rels(rels, ['was_written_in'])
    grimoires = helpers.extract_rel_list(rels, 'grimoire', 'start')
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
    data['relationships'] = exclude_rels(rels, ['published', 'edited', 'has'])
    publisher = helpers.extract_rel_list(rels, 'publisher', 'start')
    if publisher:
        data['details']['publisher'] = extract_details(publisher)

    editors = helpers.extract_rel_list(rels, 'editor', 'start')
    if editors:
        data['details']['editor'] = extract_details(editors)

    grimoire = helpers.extract_rel_list(rels, 'grimoire', 'start')
    if grimoire:
        data['details']['grimoire'] = extract_details(grimoire)

    book = helpers.extract_rel_list(rels, 'book', 'start')
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
    data['relationships'] = exclude_rels(rels, ['published'])
    books = helpers.extract_rel_list(rels, 'edition', 'end')
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
    data['relationships'] = exclude_rels(rels, ['edited'])
    editions = helpers.extract_rel_list(rels, 'edition', 'end')
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
    data['relationships'] = exclude_rels(rels, ['for'])
    grimoires = helpers.extract_rel_list(rels, 'grimoire', 'start') + \
                helpers.extract_rel_list(rels, 'book', 'start')
    data['details']['grimoire'] = extract_details(grimoires)

    outcomes = helpers.extract_rel_list_by_type(rels, 'for', 'outcome', 'end')
    if outcomes:
        data['details']['Outcome'] = extract_details(outcomes)

    return data


def exclude_rels(rels, exclusions):
    ''' remove relationships for a list of types
    :param rels: default relationship list
    :param exclusions:
    :return: customized data for this label
    '''
    return [r for r in rels if not r['type'] in exclusions]


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
                                               other['properties']['uid'],
                                               node['properties']['uid'])
            if other_items['nodes']:
                others.append({
                    'title': 'Other %s related to the %s %s' %
                             (helpers.pluralize(label), helpers.format_filter(other['label']),
                              other['properties']['identifier']),
                    'data': other_items['nodes']
                })
    return others


def extract_details(items):
    ''' format the details object
    :param items: the extracted rel list for the category
    :return: array in the format [{'text': 'John Constantine', 'link': '/person/constantine'}]
    '''
    return [{'text': i['properties']['identifier'], 'link': i['link']}
            for i in items]
