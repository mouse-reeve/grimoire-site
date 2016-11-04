''' neo4j logic '''
from grimoire import graph
from grimoire.api_serializer import serialize


class APIGraphService(object):
    ''' manage neo4j data operations '''

    def __init__(self):
        self.query = graph.query


    @serialize
    def get_label(self, label, **kwargs):
        ''' load all nodes with a given label
        :param label: the label for the type of node desired
        :param limit: result limit (max 100)
        :param offset: offset results
        :return: a serialized list of relevent nodes
        '''
        start = 'MATCH (n:%s) ' % label
        middle = ''
        return_str = 'RETURN n '
        order = ''

        if kwargs.get('random'):
            middle = 'WITH n, rand() AS r '
            order = 'ORDER BY r '

        if kwargs.get('uids_only'):
            return_str = 'RETURN n.uid '

        # only sort non-randomized queries
        if kwargs.get('sort') and not kwargs.get('random'):
            order = 'ORDER BY n.%s %s ' % \
                     (kwargs.get('sort'),
                      kwargs.get('sort_direction'))

        order += 'SKIP {offset} LIMIT {limit}'

        query = start + middle + return_str + order
        return self.query(query,
                          offset=kwargs.get('offset'),
                          limit=kwargs.get('limit'))


    @serialize
    def get_node(self, uid, relationships):
        ''' get data for a specific node '''
        if relationships:
            query = 'MATCH (n)-[r]-() WHERE n.uid={uid} '\
                    'RETURN n, r'
        else:
            query = 'MATCH (n) WHERE n.uid={uid} ' \
                    'RETURN n'
        return self.query(query, uid=uid)


    @serialize
    def get_connected_nodes(self, uid, label, **kwargs):
        ''' get data for a specific node '''
        start = 'MATCH (n)--(m:%s) WHERE n.uid={uid} ' % label
        middle = ''
        return_str = 'RETURN m '
        order = ''

        if kwargs.get('random'):
            middle = 'WITH m, rand() AS r '
            order = 'ORDER BY r '

        order += 'SKIP {offset} LIMIT {limit} '
        query = start + middle + return_str + order
        return self.query(query, uid=uid,
                          offset=kwargs.get('offset'),
                          limit=kwargs.get('limit'))
