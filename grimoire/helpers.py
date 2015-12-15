""" data formatting helper functions """
import re

from grimoire import app


def grimoire_date(props):
    """
    get a nicely formatted year for a grimoire
    :param props:
    :return:
    """
    if 'year' in props and props['year']:
        date = props['year']
    elif 'decade' in props and props['decade']:
        date = '%ss' % props['decade']
    elif 'century' in props and props['century']:
        try:
            cent = int(props['century'][:-2])
            date = '%dth century' % (cent + 1)
        except ValueError:
            date = '%ss' % props['century']
    else:
        date = ''

    return date


def sanitize(text, allow_spaces=False):
    """
    don't let any fuckery in to neo4j
    :param text:
    :param allow_spaces:
    :return:
    """
    regex = r'[a-zA-z\-\d]'
    if allow_spaces:
        regex = r'[a-zA-z\-\s\d]'
    return ''.join([t.lower() for t in text if re.match(regex, t)])


def extract_rel_list(rels, label, position):
    """
    get all relationships to a node for a given label
    :param rels:
    :param label:
    :param position:
    :return:
    """
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label]


def extract_rel_list_by_type(rels, rel_type, label, position):
    """
    get all relationships to a node for a given label and type
    :param rels:
    :param rel_type:
    :param label:
    :param position:
    :return:
    """
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label and
            r['type'] == rel_type]


# ----- filters
@app.template_filter('format')
def format_filter(rel):
    """
    cleanup _ lines
    :param rel:
    :return:
    """
    if not rel:
        return rel
    return re.sub('_', ' ', rel)


@app.template_filter('capitalize')
def capitalize_filter(text):
    """
    capitalize words
    :param text:
    :return:
    """
    text = format_filter(text)
    return text[0].upper() + text[1:]


@app.template_filter('pluralize')
def pluralize(text):
    """
    fishs
    :param text:
    :return:
    """
    text = format_filter(text)
    if text == 'person':
        return 'people'
    if text[-1] == 'y':
        return text[:-1] + 'ies'
    elif text[-1] in ['h', 's']:
        return text + 'es'
    return text + 's'
