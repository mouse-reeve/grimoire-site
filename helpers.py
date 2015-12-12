''' data formatting helper functions '''
import re

def grimoire_date(props):
    ''' get a nicely formatted year for a grimoire '''
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
    ''' don't let any fuckery in to neo4j '''
    regex = r'[a-zA-z\-\d]'
    if allow_spaces:
        regex = r'[a-zA-z\-\s\d]'
    return ''.join([t.lower() for t in text if re.match(regex, t)])


def extract_rel_list(rels, label, position):
    ''' get all relationships to a node for a given label '''
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label]


def extract_rel_list_by_type(rels, rel_type, label, position):
    ''' get all relationships to a node for a given label and type '''
    return [r[position] for r in rels
            if r[position]['label'] and r[position]['label'] == label
            and r['type'] == rel_type]

