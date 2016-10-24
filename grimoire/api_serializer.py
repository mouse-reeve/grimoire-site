''' process neo4j results '''
from py2neo import Node, Relationship
from py2neo.packages.httpstream.http import SocketError
from grimoire import internal_labels

def serialize(func):
    ''' serialize neo4j data '''

    def serialize_wrapper(self, *args, **kwargs):
        ''' serialize dis '''
        try:
            data = func(self, *args, **kwargs)
        except SocketError:
            return {}

        response = {'nodes': [], 'rels': [], 'lists': []}

        for row in data:
            for column in data.columns:
                item = row[column]
                if isinstance(item, Node):
                    response['nodes'].append(serialize_node(item))
                elif isinstance(item, Relationship):
                    response['rels'].append(serialize_relationship(item))
                elif isinstance(item, unicode):
                    response['lists'].append(item)

        return response

    return serialize_wrapper


def serialize_node(node):
    ''' node contents
    :param node: the node to serialize
    :return: a json object representing the node
    '''
    labels = [l for l in node.labels]
    parent_label = [l for l in labels if 'parent' in l]
    parent_label = parent_label[0] if len(parent_label) > 0 else None
    main_label = [l for l in labels if 'parent' not in l][0]
    link = '/%s/%s' % (main_label, node.properties['uid'])

    props = {k: v for (k, v) in node.properties.items() if check_prop_blacklist(main_label, k)}
    return {
        'id': node._id,
        'parent_label': parent_label,
        'label': main_label,
        'link': link,
        'props': props
    }


def check_prop_blacklist(label, key):
    ''' don't return content on external-facing nodes '''
    if label in internal_labels:
        return True
    return key != 'content'


def serialize_relationship(rel):
    ''' relationship contents
    :param rel: the relationship to serialize
    :return: a json object representing the relationship
    '''
    return {
        'id': rel._id,
        'start': rel.start_node.properties['uid'],
        'end': rel.end_node.properties['uid'],
        'type': rel.type
    }

