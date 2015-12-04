''' process neo4j results '''
from py2neo.packages.httpstream.http import SocketError

def serialize(func):
    ''' serialize neo4j data '''
    def serialize_wrapper(self, *args, **kwargs):
        ''' serialize dis '''
        try:
            data = func(self, *args, **kwargs)
        except SocketError:
            return {}
        nodes = []
        rels = []
        try:
            data.records
        except AttributeError:
            return {'nodes': []}

        for item in data.records:
            try:
                item_rels = item['r']
            except AttributeError:
                pass
            else:
                if item_rels:
                    for rel in item_rels:
                        rels.append({
                            'id': rel._id,
                            'start': serialize_node(rel.start_node),
                            'end': serialize_node(rel.end_node),
                            'type': rel.type,
                            'properties': rel.properties
                        })
            try:
                node = item['n']
            except AttributeError:
                pass
            else:
                nodes.append(serialize_node(node))

        return {'nodes': nodes, 'relationships': rels}
    return serialize_wrapper

def serialize_node(node):
    ''' node contents '''
    label = [l for l in node.labels][0]
    link = '/%s/%s' % (label, node.properties['uid'])
    return {
        'id': node._id,
        'label': label,
        'link': link,
        'properties': node.properties
    }
