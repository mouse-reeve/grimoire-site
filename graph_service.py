''' neo4j logic '''
import logging
import os
from py2neo import authenticate, Graph
from py2neo.packages.httpstream.http import SocketError

def serialize(func):
    ''' serialize neo4j data '''
    def serialize_wrapper(self, *args):
        ''' serialize dis '''
        data = func(self, *args)
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
                try:
                    link = '/%s/%s' % (node.labels.copy().pop(), node.properties['uid'])
                except KeyError:
                    link = ''

                nodes.append({
                    'id': node._id,
                    'labels': [l for l in node.labels],
                    'link': link,
                    'properties': node.properties,
                })

        return {'nodes': nodes, 'relationships': rels}
    return serialize_wrapper

class GraphService(object):
    ''' manage neo4j data operations '''

    def __init__(self):
        user = os.environ['NEO4J_USER']
        password = os.environ['NEO4J_PASS']
        authenticate('localhost:7474', user, password)
        try:
            graph = Graph()
            self.query = graph.cypher.execute
        except SocketError:
            logging.error('neo4j failed to load')
            self.query = lambda x: {}


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
    def get_node(self, uid):
        ''' load data '''
        node = self.query('MATCH n WHERE n.uid = "%s" OPTIONAL MATCH (n)-[r]-() RETURN n, r' % uid)
        return node


    @serialize
    def random(self):
        ''' select one random node '''
        node = self.query('MATCH n RETURN n, rand() as random ORDER BY random limit 1')
        return node
