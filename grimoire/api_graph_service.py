''' neo4j logic '''
from grimoire import graph
from grimoire.api_serializer import serialize


class APIGraphService(object):
    ''' manage neo4j data operations '''

    def __init__(self):
        self.query = graph.query


    @serialize
    def get_label(self, label, offset, limit, uids_only):
        ''' load all nodes with a given label
        :param label: the label for the type of node desired
        :param limit: result limit (max 100)
        :param offset: offset results
        :return: a serialized list of relevent nodes
        '''
        query = 'MATCH (n:%s) ' % label
        if uids_only:
            query += 'RETURN DISTINCT n.uid '
        else:
            query += 'RETURN DISTINCT n '
        query += 'SKIP {offset} LIMIT {limit}'
        return self.query(query, offset=offset, limit=limit)


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
