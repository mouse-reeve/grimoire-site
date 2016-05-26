''' data formatting helper functions '''
import re
from flask import render_template as flask_render_template
import logging

from grimoire import app, graph, templates


def grimoire_date(props):
    '''
    get a nicely formatted year for a grimoire
    :param props: all the properties for a grimoire node
    :return: a string formatted date ("2015", "2010s", or "20th century")
    '''
    try:
        date = int(props['date'])
    except ValueError:
        return date

    precision = props['date_precision']

    if precision == 'decade':
        return '%ds' % date
    elif precision == 'century':
        return '%dth century' % (date / 100 + 1)

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
    :param label: the neo4j label string of the desired items
    :param position: "start" or "end" - the position in the relationship
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
        letter = node['properties']['identifier'][0].upper()
        buckets[letter] = [node] if letter not in buckets else buckets[letter] + [node]

    return buckets

@app.template_filter('trim')
def trim_filter(text):
    ''' shorten text for breadcrumbs '''
    shorter = ' '.join(text.split(' ')[:4])
    shorter += '...' if len(shorter) < len(text) else ''
    return shorter


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
        'relationships': result['relationships']
    }
