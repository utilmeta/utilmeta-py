from tests.conftest import setup_service

setup_service(__name__, backend='django', async_param=[False])


class TestLog:
    def test_parse_values(self, service):
        from utilmeta.ops.log import Logger
        logger = Logger()
        assert (logger.parse_values([{'user': {'password': '123', 'token': 'XXX'}}]) ==
                [{'user': {'password': '********', 'token': '********'}}])
        assert (logger.parse_values([{'user': {'UserPassword': '123', 'Access_Token': 'XXX'}}]) ==
                [{'user': {'UserPassword': '********', 'Access_Token': '********'}}])
