from utilmeta.bin.commands.base import BaseServiceCommand
from utilmeta.bin.base import command
from .config import Operations
from utilmeta.bin.base import Arg
import base64


class OperationsCommand(BaseServiceCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = self.service.get_config(Operations)
        # self.settings.setup(self.service)
        self.service.setup()        # setup here

    @command
    def migrate_ops(self):
        """
        Migrate all required tables for UtilMeta Operations to the database
        """
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'migrate', 'ops', f'--database={self.config.db_alias}'])
        # 2. migrate for main database
        execute_from_command_line(['manage.py', 'migrate', 'ops'])

    @command
    def connect(self,
                to: str = None,
                key: str = Arg(required=True)
                ):
        """
        Connect your API service to UtilMeta platform to manage
        """
        self.migrate_ops()
        # before connect
        from .connect import connect_supervisor

        if not key.startswith('{') or not key.endswith('}'):
            # BASE64
            key = base64.decodebytes(key.encode()).decode()

        connect_supervisor(
            key=key,
            base_url=to
        )

    @command
    def delete_supervisor(self, node: str = Arg(required=True), key: str = Arg(required=True)):
        """
        Connect your API service to UtilMeta platform to manage
        """
        # self.migrate_ops()
        # before connect
        from .connect import delete_supervisor

        if not key.startswith('{') or not key.endswith('}'):
            # BASE64
            key = base64.decodebytes(key.encode()).decode()

        delete_supervisor(
            key=key,
            node_id=node
        )

    @command
    def sync(self, force: bool = Arg('-f', default=False)):
        """
        Sync APIs to supervisor
        """
        manager = self.config.resources_manager_cls(service=self.service)
        manager.sync_resources(force=force)

    @command
    def delete(self, node_id: str, token: str = Arg(required=True)):
        """
        delete supervisor
        """

    @command
    def stats(self):
        """
        View the current stats
        """
        pass
