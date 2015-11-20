''' neo4j logic '''
from py2neo import Graph

def serialize(func):
    ''' serialize neo4j data '''
    def serialize_wrapper(self, label):
        ''' serialize dis '''
        data = func(self, label)
        nodes = []
        rels = []
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
                            'start': {
                                'id': rel.start_node._id,
                                'labels':  [l for l in rel.start_node.labels],
                                'properties': rel.start_node.properties
                            },
                            'end': {
                                'id': rel.end_node._id,
                                'labels':  [l for l in rel.end_node.labels],
                                'properties': rel.end_node.properties
                            },
                            'type': rel.type,
                            'properties': rel.properties
                        })
            try:
                node = item['n']
            except AttributeError:
                pass
            else:
                nodes.append({
                    'id': node._id,
                    'labels': [l for l in node.labels],
                    'properties': node.properties,
                })

        return {'nodes': nodes, 'relationships': rels}
    return serialize_wrapper

class GraphService(object):
    ''' manage neo4j data operations '''

    def __init__(self):
        graph = Graph()
        self.query = graph.cypher.execute

    def get_labels(self):
        ''' list of all types/labels in the db '''
        data = self.query('MATCH n RETURN DISTINCT LABELS(n)')
        return [l[0][0] for l in data]

    @serialize
    def get_all(self, label):
        ''' load all nodes with a given label '''
        data = self.query('MATCH (n:%s) RETURN n' % label)
        return data


    @serialize
    def get_node(self, node_id):
        ''' load data '''
        node = self.query('MATCH n WHERE id(n) = %s OPTIONAL MATCH (n)-[r]-() RETURN n, r' %
                          node_id)
        return node
