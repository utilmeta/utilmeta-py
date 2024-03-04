from .client import SupervisorClient, SupervisorBasic
from utilmeta import __version__
from concurrent.futures import ThreadPoolExecutor, wait
from utilmeta.utils import exceptions, localhost
from typing import Optional
from .models import Supervisor
from .config import Operations
from .schema import SupervisorData
from .resources import ResourcesManager

# 1. meta connect --token=<ACCESS_TOKEN>
# 2,

TRUSTED_HOST = 'utilmeta.com'
DEFAULT_SUPERVISOR = 'https://api.utilmeta.com/spv'
CLIENT_NAME = f'utilmeta-py-{__version__}'

default_supervisor = SupervisorClient(
    base_url=DEFAULT_SUPERVISOR,
    base_headers={
        'User-Agent': CLIENT_NAME
    },
    fail_silently=True
)
# can only get the basic info


def auto_select_supervisor(*supervisors: SupervisorBasic, timeout: int = 5, times: int = 2) -> Optional[str]:
    if not supervisors:
        return None
    if len(supervisors) == 1:
        return supervisors[0].base_url

    url_map = {}

    def fetch_supervisor_info(base_url: str):
        with SupervisorClient(base_url=base_url, fail_silently=True) as client:
            resp = client.get_info()
            if resp.success:
                url_map.setdefault(base_url, []).append(resp.duration_ms)

    with ThreadPoolExecutor() as pool:
        tasks = []
        for supervisor in supervisors:
            for i in range(0, times):
                tasks.append(pool.submit(fetch_supervisor_info, supervisor.base_url))
        wait(tasks, timeout=timeout)

    if not url_map:
        return None

    ts_pairs = [(url, sum(durations) / len(durations)) for url, durations in url_map.items()]
    ts_pairs.sort(key=lambda v: v[1])
    return ts_pairs[0][0]


def save_supervisor(data: SupervisorData) -> Supervisor:
    if data.init_key:
        # from command line
        obj: Supervisor = Supervisor.objects.filter(
            init_key=data.init_key,
            ops_api=data.ops_api
        ).first()
        if not obj or obj.disabled:
            raise exceptions.NotFound('Supervisor not found or disabled')
        if obj.base_url != data.base_url:
            raise exceptions.Conflict('Supervisor base_url conflicted')
        if Supervisor.objects.filter(
            base_url=data.base_url,
            node_id=data.node_id
        ).exists():
            raise exceptions.Conflict(f'Supervisor[{data.node_id}] at {data.base_url} already exists')
        Supervisor.objects.filter(id=obj.pk).update(
            ident=data.ident,
            node_id=data.node_id,
            public_key=data.public_key,
            backup_urls=data.backup_urls,
            connected=True,
            url=data.url,
            local=data.local,
        )
        return Supervisor.objects.filter(id=obj.pk).first()     # refresh
    else:
        # from api calling
        raise NotImplementedError


def connect_supervisor(
    key: str,
    base_url: str = None,
):
    from utilmeta import service
    ops_config = Operations.config()
    if not ops_config:
        raise TypeError('Operations not configured')

    if not base_url:
        # get action url based on the latency
        # fire 2 request for each supervisor at the same time, choose the more reliable one
        print('connecting: auto-selecting supervisor...')
        list_resp = default_supervisor.get_supervisors()
        if list_resp.success:
            base_url = auto_select_supervisor(*list_resp.result)
    else:
        ops_config.check_supervisor(base_url)

    if not base_url:
        raise ValueError('No supervisor selected, operation failed')

    if service.production:
        if not ops_config.check_host():
            raise ValueError(f'Invalid production service operations location: {ops_config.ops_api}, '
                             f'please use UtilMeta(origin="https://YOUR-PUBLIC-HOST") '
                             f'to specify your public accessible service origin')

    print(f'connect supervisor at: {base_url}')

    # with orm.Atomic(ops_config.db_alias):
    # --- PLACEHOLDER
    ops_api = ops_config.ops_api

    supervisor_obj = Supervisor.objects.filter(
        service=service.name,
        base_url=base_url,
        ops_api=ops_api
    ).first()

    if supervisor_obj:
        if supervisor_obj.local:
            print(f'local supervisor already exists as [{supervisor_obj.node_id}], visit it in {supervisor_obj.url}')
            return

        if supervisor_obj.public_key:
            print(f'supervisor for {base_url} already exists as [{supervisor_obj.node_id}],'
                  f' visit it in {supervisor_obj.url}')
            return

        if supervisor_obj.init_key != key:
            supervisor_obj.init_key = key
            supervisor_obj.save(update_fields=['init_key'])

    if not supervisor_obj:
        supervisor_obj = Supervisor.objects.create(
            service=service.name,
            base_url=base_url,
            init_key=key,       # for double-check
            ops_api=ops_api
        )

    resources = ResourcesManager(service)
    url = None

    try:
        with SupervisorClient(
            base_url=base_url,
            access_key=key,
            fail_silently=True
        ) as cli:
            resp = cli.add_node(
                data=resources.get_metadata()
            )
            if not resp.success:
                raise ValueError(f'connect to supervisor failed with error: {resp.message}')

            if resp.result:
                # supervisor is returned (cannot access)
                supervisor_obj = save_supervisor(resp.result)
            else:
                # supervisor already updated in POST OperationsAPI/
                supervisor_obj: Supervisor = Supervisor.objects.get(pk=supervisor_obj.pk)

            # update after
            if not supervisor_obj.node_id:
                raise ValueError('supervisor failed to create')
            if supervisor_obj.node_id != resp.result.node_id:
                raise ValueError(f'supervisor failed to create: inconsistent node id: '
                                 f'{supervisor_obj.node_id}, {resp.result.node_id}')

            if not supervisor_obj.local:
                if not supervisor_obj.public_key:
                    raise ValueError('supervisor failed to create: no public key')
            else:
                if not localhost(ops_api):
                    raise ValueError(f'supervisor failed to create: invalid local supervisor for {ops_api}')

            url = supervisor_obj.url
            print(f'supervisor[{supervisor_obj.node_id}] created')
    except Exception as e:
        supervisor_obj.delete()
        raise e

    if not supervisor_obj.local:
        resources.sync_resources(supervisor_obj)

    print('supervisor connected successfully!')
    if url:
        print(f'please visit {url} to view and manage your APIs')
