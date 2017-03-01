''' data formatting helper functions '''
import copy
import logging
from markdown import markdown
import re

from flask import render_template as flask_render_template

from grimoire import app, graph, templates


def grimoire_date(props, date_key='date'):
    '''
    get a nicely formatted year for a grimoire
    :param props: all the properties for a grimoire node
    :param date_key: the name of the property that represents the date (ie "born")
    :return: a string formatted date ("2015", "2010s", or "20th century")
    '''
    try:
        date = int(props[date_key])
    except ValueError:
        return props[date_key]
    except KeyError:
        return None

    precision = props['date_precision']

    if precision == 'decade':
        return '%ds' % date
    elif precision == 'century':
        century = date / 100 + 1
        if century == 1:
            return '1st century'
        elif century == 2:
            return '2nd century'
        elif century == 3:
            return '3rd century'
        return '%dth century' % century

    return date


def sanitize(text, allow_spaces=False):
    ''' don't let any fuckery in to neo4j
    :param text: a string to be used in a neo4j query
    :param allow_spaces: prevents removing spaces (eg, for search)
    :return: the white-list characters from the input text
    '''
    regex = r'[a-zA-z\-\d]'
    if allow_spaces:
        regex = r'[a-zA-z\-\s\d]'
    return ''.join([t.lower() for t in text if re.match(regex, t)])


def extract_rel_list(rels, label, position):
    ''' get all relationships to a node for a given label
    :param rels: the serialized rels object
    :param label: the neo4j label string of the desired items
    :param position: "start" or "end" - the position in the relationship
    :return: a list of nodes
    '''
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label
            or r[position]['parent_label'] and r[position]['parent_label'] == label]


def extract_rel_list_by_type(rels, rel_type, position, label=None):
    ''' get all relationships to a node for a given label and type
    :param rels: the serialized rels object from neo4j
    :param rel_type: specify a rel type ([r:lists], for example)
    :param position: "start" or "end" - the position in the relationship
    :param label: the neo4j label string of the desired items
    :return: a list of nodes
    '''
    return [r[position] for r in rels if
            (not label or
             (r[position]['label'] and r[position]['label'] == label or
              r[position]['parent_label'] and r[position]['parent_label'] == label)) and
            r['type'] == rel_type]


# ----- filters
@app.template_filter('format')
def format_filter(text):
    ''' cleanup _ lines
    :param text: a relationship or category, or whatever contains an _
    :return: a string with _ replaced with a space
    '''
    if not text:
        return text
    return re.sub('_', ' ', text)


@app.template_filter('capitalize')
def capitalize_filter(text):
    ''' capitalize words
    :param text: a string
    :return: that string with the first letter only capitalized
    '''
    text = format_filter(text)
    if not text:
        return text
    return text[0].upper() + text[1:]


@app.template_filter('pluralize')
def pluralize(text):
    ''' fishs
    :param text: a singular english word
    :return: that world, algorithmically pluralized
    '''
    text = format_filter(text)
    if text == 'person':
        return 'people'
    if text[-1] == 'y':
        return text[:-1] + 'ies'
    elif text[-1] in ['h', 's']:
        return text + 'es'
    return text + 's'


@app.template_filter('unthe')
def unthe(text):
    ''' Re-orders "Book, The" and "Last, First" names
    :param text: the comma-containing string
    :return: an untangled string, or the original if there isn't 1 comma
    '''
    text = format_filter(text)
    pieces = text.split(', ')
    if not len(pieces) == 2:
        return text

    return '%s %s' % (pieces[1], pieces[0])


@app.template_filter('shortlink')
def shortlink(url):
    ''' create shorter text for parsed urls in templates '''
    try:
        parts = url.split('/')
        domain = parts[2]
        if url.split('.')[-1] == 'pdf':
            domain += ' (pdf)'
        return domain
    except IndexError:
        return url


@app.template_filter('alphabuckets')
def alphabuckets(items):
    ''' sort items into letter "buckets" for alphabetizing '''
    buckets = {}
    for node in items:
        letter = node['props']['identifier'][0].upper()
        buckets[letter] = [node] if letter not in buckets else buckets[letter] + [node]

    return buckets


@app.template_filter('trim')
def trim_filter(text):
    ''' shorten text for breadcrumbs '''
    shorter = ' '.join(text.split(' ')[:4])
    shorter += '...' if len(shorter) < len(text) else ''
    return shorter


@app.template_filter('markdown')
def mardown_filter(text):
    return markdown(text)


def load_cached_template(url):
    ''' render a template if necessary '''
    return templates[url] or None


def render_template(url, template, **kwargs):
    ''' store a rendered template '''
    templates[url] = flask_render_template(template, **kwargs)
    return templates[url]


def get_node(uid):
    ''' get a node or return an error '''
    logging.info('loading %s', uid)
    uid = sanitize(uid)
    result = graph.get_node(uid)

    if 'nodes' not in result or not result['nodes']:
        logging.error('Invalid uid %s', uid)
        raise NameError('node not found')

    return {
        'node': result['nodes'][0],
        'rels': result['rels']
    }


def exclude_rels(rels, exclusions):
    ''' remove relationships for a list of types
    :param rels: default relationship list
    :param exclusions:
    :return: customized data for this label
    '''
    return [r for r in rels if not r['type'] in exclusions]


def combine_rels(rels):
    ''' merge relationships of the same type, for better readability
    :param rels: the relationships remaining after the item is processed
    :return: list of rels containing lists and start/ends
    '''
    types = {}
    for rel in rels:
        key = rel['start']['label'] + rel['type']
        types[key] = types[key] + [rel] if key in types else [rel]

    result = []
    for rels in types.values():
        result.append({
            'start': [r['start'] for r in rels],
            'end': [r['end'] for r in rels],
            'type': rels[0]['type']
        })
    return result


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
                timeline = add_to_timeline(
                    timeline, event,
                    event['props']['date'],
                    event['props']['date_precision'],
                    note=note,
                    allow_events=True)
    return timeline, timeline_min, timeline_max


def add_to_timeline(timeline, node, year, date_precision, note=None, allow_events=False):
    ''' put a date on it
    :param timeline: the existing timeline object
    :param year: the year/decade/century of origin
    :param date_precision: how precide the date is (year/decade/century)
    :param node: the node
    :param note: display text to go along with the node (if available)
    :param allow_events: if nodes of type "event" should appear in timeline
    :return: updated timeline object
    '''
    if not allow_events and node['label'] == 'event':
        return timeline
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
