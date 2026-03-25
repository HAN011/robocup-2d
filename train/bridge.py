from __future__ import annotations

import os
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from multiprocessing.managers import SyncManager

from train import config


@dataclass(frozen=True)
class BridgeAddress:
    host: str
    port: int
    authkey: str


class _BridgeServerManager(SyncManager):
    pass


class _BridgeClientManager(SyncManager):
    pass


_server_state_queue: queue.Queue | None = None
_server_action_queue: queue.Queue | None = None
_server_manager = None
_server_thread: threading.Thread | None = None
_client_manager = None
_bridge_address: BridgeAddress | None = None

state_queue = None
action_queue = None


def _get_server_state_queue():
    return _server_state_queue


def _get_server_action_queue():
    return _server_action_queue


_BridgeServerManager.register("get_state_queue", callable=_get_server_state_queue)
_BridgeServerManager.register("get_action_queue", callable=_get_server_action_queue)
_BridgeClientManager.register("get_state_queue")
_BridgeClientManager.register("get_action_queue")


def start_bridge_server(
    host: str = config.BRIDGE_HOST,
    port: int = 0,
    authkey: str | None = None,
    queue_maxsize: int = config.BRIDGE_QUEUE_MAXSIZE,
) -> BridgeAddress:
    global _bridge_address
    global _client_manager
    global _server_action_queue
    global _server_manager
    global _server_state_queue
    global _server_thread
    global action_queue
    global state_queue

    if _bridge_address is not None:
        return _bridge_address

    authkey = authkey or secrets.token_hex(16)
    _server_state_queue = queue.Queue(maxsize=queue_maxsize)
    _server_action_queue = queue.Queue(maxsize=queue_maxsize)
    _server_manager = _BridgeServerManager(address=(host, port), authkey=authkey.encode("utf-8"))
    server = _server_manager.get_server()
    _server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="robocup-rl-bridge")
    _server_thread.start()

    actual_host, actual_port = server.address
    _bridge_address = BridgeAddress(host=str(actual_host), port=int(actual_port), authkey=authkey)
    connect_bridge_client(_bridge_address.host, _bridge_address.port, _bridge_address.authkey)
    return _bridge_address


def connect_bridge_client(host: str, port: int, authkey: str):
    global _bridge_address
    global _client_manager
    global action_queue
    global state_queue

    if (
        _client_manager is not None
        and _bridge_address is not None
        and _bridge_address.host == host
        and _bridge_address.port == int(port)
        and _bridge_address.authkey == authkey
    ):
        return _client_manager

    manager = _BridgeClientManager(address=(host, int(port)), authkey=authkey.encode("utf-8"))
    manager.connect()
    _client_manager = manager
    _bridge_address = BridgeAddress(host=str(host), port=int(port), authkey=authkey)
    state_queue = manager.get_state_queue()
    action_queue = manager.get_action_queue()
    return manager


def ensure_bridge_client_from_env():
    host = os.environ.get(config.BRIDGE_HOST_ENV, "").strip()
    port = os.environ.get(config.BRIDGE_PORT_ENV, "").strip()
    authkey = os.environ.get(config.BRIDGE_AUTHKEY_ENV, "").strip()
    if not host or not port or not authkey:
        return None
    return connect_bridge_client(host, int(port), authkey)


def _remaining_seconds(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def put_state_message(message: dict, timeout: float) -> bool:
    if state_queue is None and ensure_bridge_client_from_env() is None:
        return False
    try:
        state_queue.put(message, timeout=timeout)
    except queue.Full:
        return False
    return True


def put_action_message(message: dict, timeout: float) -> bool:
    if action_queue is None:
        return False
    try:
        action_queue.put(message, timeout=timeout)
    except queue.Full:
        return False
    return True


def get_action_message(episode_id: str, request_id: int, timeout: float) -> dict | None:
    if action_queue is None and ensure_bridge_client_from_env() is None:
        return None

    deadline = time.monotonic() + timeout
    while True:
        remaining = _remaining_seconds(deadline)
        if remaining <= 0.0:
            return None
        try:
            message = action_queue.get(timeout=remaining)
        except queue.Empty:
            return None

        if str(message.get("episode_id", "")) != episode_id:
            continue
        if int(message.get("request_id", -1)) != int(request_id):
            continue
        return message


def get_state_message(
    timeout: float,
    episode_id: str | None = None,
    min_request_id: int | None = None,
) -> dict | None:
    if state_queue is None:
        return None

    deadline = time.monotonic() + timeout
    while True:
        remaining = _remaining_seconds(deadline)
        if remaining <= 0.0:
            return None
        try:
            message = state_queue.get(timeout=remaining)
        except queue.Empty:
            return None

        if episode_id is not None and str(message.get("episode_id", "")) != str(episode_id):
            continue
        if min_request_id is not None and int(message.get("request_id", -1)) < int(min_request_id):
            continue
        return message


def drain_queue(target_queue) -> None:
    if target_queue is None:
        return
    while True:
        try:
            target_queue.get_nowait()
        except queue.Empty:
            return


def drain_bridge_queues() -> None:
    drain_queue(state_queue)
    drain_queue(action_queue)


def bridge_address() -> BridgeAddress | None:
    return _bridge_address
