''' neo4j logic '''
import logging
import os
from py2neo import authenticate, Graph
from py2neo.packages.httpstream.http import SocketError
from serializer import serialize

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
        labels = self.query('MATCH n RETURN DISTINCT LABELS(n)')
        self.labels = [l[0][0] for l in labels]


    def get_labels(self):
        ''' list of all types/labels in the db '''
        return self.labels


    def validate_label(self, label):
        ''' check if a label is real '''
        return label in self.labels


    @serialize
    def get_all(self, label):
        ''' load all nodes with a given label '''
        data = self.query('MATCH (n:%s) RETURN n' % label)
        return data


    @serialize
    def get_node(self, uid):
        ''' load data '''
        node = self.query('MATCH n WHERE n.uid = {uid} OPTIONAL MATCH (n)-[r]-() RETURN n, r',
                          uid=uid)
        return node


    @serialize
    def random(self):
        ''' select one random node '''
        node = self.query('MATCH n RETURN n, rand() as random ORDER BY random limit 1')
        return node


    @serialize
    def search(self, term):
        ''' match a search term '''
        data = self.query('match n where n.identifier =~ {term} or ' \
                          'n.alternate_names =~ {term} or ' \
                          'n.content =~ {term} return n', term='(?i).*%s.*' % term)
        return data

    @serialize
    def related(self, uid, label, n=2, limit=5):
        ''' find similar items, based on nth degree relationships '''
        query = 'match (m)-[r*%d]-(n:%s) where m.uid = {uid} ' \
                'return distinct n, count(r) order by count(r) desc ' \
                'limit %d' % (n, label, limit)
        return self.query(query, uid=uid)

