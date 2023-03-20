from neo4j import GraphDatabase, basic_auth
import logging

class Neo4jLogger(logging.Handler):
    def __init__(self, uri, user, password, user_actions=None):
        super().__init__()
        self.driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
        self.user_actions = user_actions if user_actions else ['login', 'logout', 'create', 'update', 'delete']
        
    def emit(self, record):
        session = self.driver.session()
        try:
            data = self.format(record).split('|')
            user_id = data[0]
            user_action = data[1]
            category = data[2]
            data_of_interest = data[3]
            if user_action not in self.user_actions:
                raise ValueError(f'Invalid user action: {user_action}')
            session.run("CREATE (:Log {user_id: $user_id, user_action: $user_action, category: $category, data_of_interest: $data_of_interest})",
                        user_id=user_id, user_action=user_action, category=category, data_of_interest=data_of_interest)
        finally:
            session.close()

/*
logger = logging.getLogger('mylogger')
logger.setLevel(logging.INFO)
handler = Neo4jLogger('bolt://localhost:7687', 'neo4j', 'password')
logger.addHandler(handler)

# log user data
logger.info('1234|login|security|successful login')
*/
