''' process neo4j results '''
from py2neo import Node, Relationship
from py2neo.packages.httpstream.http import SocketError


def serialize(func):
    ''' serialize neo4j data '''

    def serialize_wrapper(self, *args, **kwargs):
        ''' serialize dis '''
        try:
            data = func(self, *args, **kwargs)
        except SocketError:
            return {}

        response = {'nodes': [], 'relationships': [], 'lists': []}

        for row in data:
            for column in data.columns:
                item = row[column]
                if isinstance(item, Node):
                    response['nodes'].append(serialize_node(item))
                elif isinstance(item, Relationship):
                    response['relationships'].append(serialize_relationship(item))
                elif isinstance(item, list) and isinstance(item[0], Node):
                    response['lists'].append([serialize_node(n) for n in item])

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
    main_label = [l for l in labels if not 'parent' in l][0]
    link = '/%s/%s' % (main_label, node.properties['uid'])
    return {
        'id': node._id,
        'parent_label': parent_label,
        'label': main_label,
        'link': link,
        'properties': node.properties
    }


def serialize_relationship(rel):
    ''' relationship contents
    :param rel: the relationship to serialize
    :return: a json object representing the relationship
    '''
    return {
        'id': rel._id,
        'start': serialize_node(rel.start_node),
        'end': serialize_node(rel.end_node),
        'type': rel.type,
        'properties': rel.properties
    }
