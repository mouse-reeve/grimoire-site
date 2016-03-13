''' data formatting helper functions '''
import re

from grimoire import app


def grimoire_date(props):
    '''
    get a nicely formatted year for a grimoire
    :param props: all the properties for a grimoire node
    :return: a string formatted date ("2015", "2010s", or "20th century")
    '''
    if 'year' in props and props['year']:
        date = props['year']
    elif 'decade' in props and props['decade']:
        date = '%ss' % props['decade']
    elif 'century' in props and props['century']:
        try:
            cent = props['century']/100
            date = '%dth century' % (cent + 1)
        except ValueError:
            date = '%ss' % props['century']
    else:
        date = ''

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
            if r[position]['label'] and r[position]['label'] == label]


def extract_rel_list_by_type(rels, rel_type, label, position):
    ''' get all relationships to a node for a given label and type
    :param rels: the serialized rels object from neo4j
    :param rel_type: specify a rel type ([r:lists], for example)
    :param label: the neo4j label string of the desired items
    :param position: "start" or "end" - the position in the relationship
    :return:a list of nodes
    '''
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label and
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
