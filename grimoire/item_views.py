""" views for the item type pages """
import logging

from flask import render_template

import grimoire.helpers as helpers
from grimoire import app, graph, entities


@app.route('/<label>/<uid>')
def item(label, uid):
    """
    generic page for an item
    :param label:
    :param uid:
    :return: rendered item page template
    """

    # load and validate url data
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

    # ----- page header/metadata
    title = '%s (%s)' % (node['properties']['identifier'], helpers.capitalize_filter(label))

    # ----- formatted data
    switch = {
        'grimoire': ('grimoire.html', grimoire_item),
        'fairy': ('entity.html', entity_item),
        'demon': ('entity.html', entity_item),
        'angel': ('entity.html', entity_item),
        'aerial_spirit': ('entity.html', entity_item),
        'olympian_spirit': ('entity.html', entity_item),
        'art': ('topic.html', art_item),
        'language': ('language.html', language_item),
        'edition': ('edition.html', edition_item),
        'editor': ('editor.html', editor_item),
        'default': ('item.html', generic_item)
    }

    key = label if label in switch else 'default'
    template = switch[key][0]
    item_data = switch[key][1](node, rels)

    # ----- sidebar
    sidebar = []
    related = graph.related(uid, label)
    if related['nodes']:
        sidebar = [{'title': 'Similar %s' % helpers.pluralize(helpers.capitalize_filter(label)),
                    'data': related['nodes']}]
    sidebar += get_others(data['relationships'], node)

    return render_template('items/%s' % template,
                           data=item_data,
                           title=title,
                           label=label,
                           sidebar=sidebar)

def generic_item(node, rels):
    """
    no special template data formatting here
    :param node:
    :param rels:
    :return:
    """
    return {
        'id': node['id'],
        'properties': node['properties'],
        'relationships': rels,
        'has_details': len([k for k in node['properties'].keys()
                            if k not in ['uid', 'content', 'identifier'] and
                            node['properties'][k]]) > 0
    }

def grimoire_item(node, rels):
    """
    grimoire item page
    :param node:
    :param rels:
    :return:
    """

    data = generic_item(node, rels)

    data['properties'] = {k: v for k, v in data['properties'].items() if
                          k not in ['year', 'decade', 'century']}
    data['relationships'] = exclude_rels(rels, ['lists', 'has', 'includes'])

    data['date'] = helpers.grimoire_date(node['properties'])
    data['editions'] = helpers.extract_rel_list(rels, 'edition', 'end')
    data['spells'] = helpers.extract_rel_list(rels, 'spell', 'end')
    data['entities'] = {}
    for entity in entities:
        data['entities'][entity] = helpers.extract_rel_list_by_type(rels, 'lists', entity, 'end')
    return data

def entity_item(node, rels):
    """
     entity item page
    :param node:
    :param rels:
    :return:
    """
    data = generic_item(node, rels)

    # removes duplication of two-way sister relationships
    rels = [r for r in rels if r['type'] != 'is_a_sister_of' or r['end']['id'] != node['id']]

    data['relationships'] = exclude_rels(rels, ['lists', 'teaches', 'skilled_in', 'serves'])
    data['grimoires'] = helpers.extract_rel_list(rels, 'grimoire', 'start')
    data['skills'] = helpers.extract_rel_list(rels, 'art', 'end')
    data['serves'] = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'end')
    data['serves'] = [s for s in data['serves'] if
                      not s['properties']['uid'] == node['properties']['uid']]
    data['servants'] = helpers.extract_rel_list_by_type(rels, 'serves', 'demon', 'start')
    data['servants'] = [s for s in data['servants'] if
                        not s['properties']['uid'] == node['properties']['uid']]
    return data

def art_item(node, rels):
    """ art/topic item page
    :param node:
    :param rels:
    :return:
    """
    data = generic_item(node, rels)
    data['entities'] = {}
    for entity in entities:
        data['entities'][entity] = helpers.extract_rel_list(rels, entity, 'start')
    data['relationships'] = exclude_rels(rels, ['teaches', 'skilled_in'])
    return data

def language_item(node, rels):
    """ language item page
    :param node:
    :param rels:
    :return:
    """
    data = generic_item(node, rels)
    data['relationships'] = exclude_rels(rels, ['was_written_in'])
    data['grimoires'] = helpers.extract_rel_list(rels, 'grimoire', 'start')
    return data


def edition_item(node, rels):
    """ edition of a grimoire item page
    :param node:
    :param rels:
    :return:
    """
    data = generic_item(node, rels)
    data['relationships'] = exclude_rels(rels, ['published', 'edited', 'has'])
    data['properties'] = {k: v for k, v in node['properties'].items() if
                          not k == 'editor'}
    data['publisher'] = helpers.extract_rel_list(rels, 'publisher', 'start')
    data['editors'] = helpers.extract_rel_list(rels, 'editor', 'start')
    data['grimoire'] = helpers.extract_rel_list(rels, 'grimoire', 'start')[0]
    return data

def editor_item(node, rels):
    """ editor of a grimoire item page
    :param node:
    :param rels:
    :return:
    """
    data = generic_item(node, rels)
    data['relationships'] = exclude_rels(rels, ['edited'])
    data['editions'] = helpers.extract_rel_list(rels, 'edition', 'end')
    return data

def exclude_rels(rels, exclusions):
    """ remove relationships for a list of types
    :param rels:
    :param exclusions:
    :return:
    """
    return [r for r in rels if not r['type'] in exclusions]

def get_others(rels, node):
    """
    other items of the node's type related to something it is related to.
    For example: "Other editions by the editor Joseph H. Peterson"
    :param rels:
    :param node:
    :return:
    """
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

