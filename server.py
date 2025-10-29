import asyncio
import json
import logging
import os
import re
import socket
import time
from contextlib import asynccontextmanager
from typing import Optional

import jsonschema
import psutil
import toml
import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from zeroconf import InterfaceChoice, ServiceInfo, Zeroconf

from homedeck.utils import deep_merge

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

process: Optional[asyncio.subprocess.Process] = None

load_dotenv()
MDNS_SERVICE_ID = os.getenv('MDNS_SERVICE_ID', '').strip()

SCRIPT_NAME = 'deck.py'
SERVER_PORT = 3325  # DECK
API_VERSION = '1'
DEVICE_INFO = {}

websocket_clients = set()
websocket_lock = asyncio.Lock()


def get_local_ips():
    """
    Get all non-loopback IPv4 addresses from all network interfaces.
    """
    ips = []
    interfaces = psutil.net_if_addrs()

    for interface, addrs in interfaces.items():
        for addr in addrs:
            # Check if the address is IPv4 and not a loopback address
            if addr.family == socket.AF_INET and not addr.address.startswith('127.') and not addr.address.startswith('10.'):
                ips.append(addr.address)
    return ips


def prepare_mdns_service_info():
    local_ips = get_local_ips()

    service_type = '_homedeck._tcp.local.'
    if MDNS_SERVICE_ID:
        # Validate ID
        if not re.match(r'^[A-Za-z0-9\-\_\s]+$', MDNS_SERVICE_ID):
            print('Error: Invalid characters in env.MDNS_SERVICE_ID value!')
            os._exit(-1)
            return

        service_id = MDNS_SERVICE_ID
    else:
        service_id = 'deck-' + local_ips[0].replace(':', '-').replace('[', '').replace(']', '').replace('.', '-')

    return ServiceInfo(
        service_type,
        f'{service_id}.{service_type}',
        addresses=local_ips,
        port=SERVER_PORT,
        properties={
            'api_version': API_VERSION,
            'version': toml.load('pyproject.toml').get('project', {}).get('version', 'Unknown'),
        },
    )


def is_script_running():
    """Check if script_x.py is already running"""
    for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(SCRIPT_NAME in arg for arg in cmdline):
                return True
            # Windows fallback: check process name
            if proc.info['name'] in ('python.exe', 'python3.exe') and cmdline and SCRIPT_NAME in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


async def read_script_output():
    while True:
        if not process or not process.stdout:
            await asyncio.sleep(0.1)
            continue

        line = await process.stdout.readline()
        if not line:
            await asyncio.sleep(0.1)
            continue

        await app.state.broadcast_queue.put({
            'type': 'logs',
            'payload': {
                'timestamp': int(time.time()),
                'message': line.decode().strip(),
            },
        })

        await asyncio.sleep(0.05)


async def broadcast_messages():
    while True:
        message = await app.state.broadcast_queue.get()
        json_message = json.dumps(message)

        disconnected_clients = set()

        for client in websocket_clients:
            try:
                await client.send_text(json_message)
            except Exception:
                disconnected_clients.add(client)

        if disconnected_clients:
            async with websocket_lock:
                for client in disconnected_clients:
                    websocket_clients.discard(client)

        await asyncio.sleep(0.05)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Setup queue
    app.state.broadcast_queue = asyncio.Queue()
    broadcast_task = asyncio.create_task(broadcast_messages())

    # Run homedeck
    await start_script()
    read_task = asyncio.create_task(read_script_output())

    yield

    broadcast_task.cancel()
    read_task.cancel()


app = FastAPI(lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
)


async def broadcast_script_status():
    # Check if script is running (works for both systemd and API-started processes)
    is_running = (process is not None and process.stdout) or is_script_running()
    status = 'running' if is_running else 'stopped'
    await app.state.broadcast_queue.put({
        'type': 'status',
        'payload': {
            'status': status,
        },
    })


@app.post(f'/v{API_VERSION}/start')
async def start_script():
    global process
    if process is not None or is_script_running():
        return {'error': 'Script is already running'}

    current_dir = os.path.dirname(os.path.realpath(__file__))
    venv_python = os.path.join(current_dir, 'venv', 'bin', 'python3')
    python_cmd = venv_python if os.path.exists(venv_python) else 'python3'

    process = await asyncio.create_subprocess_exec(
        python_cmd, '-u', SCRIPT_NAME,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await broadcast_script_status()
    return {'message': 'Script started'}


@app.post(f'/v{API_VERSION}/stop')
async def stop_script():
    global process
    if process is None:
        return {'error': 'Script is not running'}

    process.terminate()
    await process.wait()
    process = None

    await broadcast_script_status()
    return {'message': 'Script stopped'}


@app.get(f'/v{API_VERSION}/configuration')
async def get_configuration():
    '''
    global process
    if process is None:
        return {'error': 'Script is not running'}'
    '''

    current_dir = os.path.dirname(os.path.realpath(__file__))
    configuration_path = os.path.join(current_dir, 'assets', 'configuration.yml')
    content = ''

    if os.path.exists(configuration_path):
        with open(configuration_path, 'r') as fp:
            content = fp.read()

    return {'data': {'content': content}}


@app.post(f'/v{API_VERSION}/configuration')
async def update_configuration(req: Request):
    data = await req.json()
    if 'content' not in data:
        return {'error': 'Missing "content"'}

    content = data['content']

    # Verify configuration
    current_dir = os.path.dirname(os.path.realpath(__file__))

    with open(os.path.join(current_dir, 'src', 'homedeck', 'yaml', 'configuration.base.yml'), 'r') as fp:
        base_configuration_dict = yaml.safe_load(fp.read())

    configuration_dict = yaml.safe_load(content)

    # Handle empty/invalid YAML
    if configuration_dict is None:
        return {'error': 'Invalid YAML: content is empty or null'}

    if not isinstance(configuration_dict, dict):
        return {'error': 'Invalid YAML: must be a dictionary'}

    configuration_dict = deep_merge(base_configuration_dict, configuration_dict)

    with open(os.path.join(current_dir, 'src', 'homedeck', 'yaml', 'configuration.schema.yml'), 'r', encoding='utf-8') as fp:
        try:
            jsonschema.validate(instance=configuration_dict, schema=yaml.safe_load(fp))

            # Save configuration
            configuration_path = os.path.join(current_dir, 'assets', 'configuration.yml')
            with open(configuration_path, 'w') as fpp:
                fpp.write(content)

            return {'data': {}}
        except jsonschema.exceptions.ValidationError:
            pass

    return {'error': 'Invalid configuration'}


@app.get(f'/v{API_VERSION}/schema')
async def get_schema():
    '''
    global process
    if process is None:
        return {'error': 'Script is not running'}'
    '''

    current_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(current_dir, 'src', 'homedeck', 'yaml', 'configuration.schema.yml'), 'r', encoding='utf-8') as fp:
        yaml_object = yaml.safe_load(fp)
        return yaml_object

    return {}


@app.websocket(f'/v{API_VERSION}/ws')
async def websocket_endpoint(websocket: WebSocket):
    global process

    await websocket.accept()
    async with websocket_lock:
        websocket_clients.add(websocket)

    try:
        await broadcast_script_status()

        while True:
            await asyncio.sleep(0.1)
    except Exception as e:
        print(e, flush=True)
    finally:
        async with websocket_lock:
            websocket_clients.discard(websocket)


@app.head(f'/v{API_VERSION}/status')
async def status_endpoint():
    return Response(status_code=200)


if __name__ == "__main__":
    # Announce mDNS service
    mdns_service_info = prepare_mdns_service_info()
    zeroconf_instance = Zeroconf(interfaces=InterfaceChoice.All)
    zeroconf_instance.register_service(mdns_service_info)

    # Start API server
    try:
        uvicorn.run(app, host='0.0.0.0', port=SERVER_PORT)
    finally:
        zeroconf_instance.unregister_service(mdns_service_info)
        zeroconf_instance.close()
