"""
Schwab streaming API client.
Source: https://github.com/tylerebowers/Schwab-API-Python
"""

import json
import atexit
import asyncio
import datetime
import threading
import websockets
from time import sleep
import websockets.exceptions


class Stream:

    def __init__(self, client):
        self._websocket = None
        self._streamer_info = None
        self._request_id = 0
        self.active = False
        self._thread = None
        self._client = client
        self.subscriptions = {}

        def stop_atexit():
            if self.active:
                self.stop()
        atexit.register(stop_atexit)

    async def _start_streamer(self, receiver_func=print, **kwargs):
        response = self._client.preferences()
        if response.ok:
            self._streamer_info = response.json().get('streamerInfo', None)[0]
        else:
            print("[Schwabdev] Could not get streamerInfo")
            return

        start_time = datetime.datetime.now(datetime.timezone.utc)
        while True:
            try:
                start_time = datetime.datetime.now(datetime.timezone.utc)
                async with websockets.connect(self._streamer_info.get('streamerSocketUrl'), ping_interval=None) as self._websocket:
                    login_payload = self.basic_request(
                        service="ADMIN", command="LOGIN",
                        parameters={
                            "Authorization": self._client.access_token,
                            "SchwabClientChannel": self._streamer_info.get("schwabClientChannel"),
                            "SchwabClientFunctionId": self._streamer_info.get("schwabClientFunctionId"),
                        })
                    await self._websocket.send(json.dumps(login_payload))
                    receiver_func(await self._websocket.recv(), **kwargs)
                    self.active = True

                    for service, subs in self.subscriptions.items():
                        reqs = []
                        for key, fields in subs.items():
                            reqs.append(self.basic_request(service=service, command="ADD",
                                                           parameters={"keys": key, "fields": Stream._list_to_string(fields)}))
                        if reqs:
                            await self._websocket.send(json.dumps({"requests": reqs}))
                            receiver_func(await self._websocket.recv(), **kwargs)

                    while True:
                        receiver_func(await self._websocket.recv(), **kwargs)

            except Exception as e:
                self.active = False
                if e is websockets.exceptions.ConnectionClosedOK or str(e) == "received 1000 (OK); then sent 1000 (OK)":
                    break
                elif e is websockets.exceptions.ConnectionClosedError or str(e) == "no close frame received or sent":
                    break
                elif (datetime.datetime.now(datetime.timezone.utc) - start_time).seconds <= 90:
                    break
                else:
                    print(f"[Schwabdev] Stream connection lost ({e}), reconnecting...")

    def start(self, receiver=print, daemon: bool = True, **kwargs):
        if not self.active:
            def _start_async():
                asyncio.run(self._start_streamer(receiver, **kwargs))
            self._thread = threading.Thread(target=_start_async, daemon=daemon)
            self._thread.start()

    def stop(self, clear_subscriptions: bool = True):
        if clear_subscriptions:
            self.subscriptions = {}
        self._request_id += 1
        self.send(self.basic_request(service="ADMIN", command="LOGOUT"))
        self.active = False

    def _record_request(self, request: dict):
        def str_to_list(st):
            if type(st) is str: return st.split(",")
            elif type(st) is list: return st
        service = request.get("service")
        command = request.get("command")
        parameters = request.get("parameters")
        if parameters is not None:
            keys = str_to_list(parameters.get("keys", []))
            fields = str_to_list(parameters.get("fields", []))
            if service not in self.subscriptions:
                self.subscriptions[service] = {}
            if command == "ADD":
                for key in keys:
                    if key not in self.subscriptions[service]:
                        self.subscriptions[service][key] = fields
                    else:
                        self.subscriptions[service][key] = list(set(fields) | set(self.subscriptions[service][key]))
            elif command == "SUBS":
                self.subscriptions[service] = {}
                for key in keys:
                    self.subscriptions[service][key] = fields
            elif command == "UNSUBS":
                for key in keys:
                    if key in self.subscriptions[service]:
                        self.subscriptions[service].pop(key)

    def send(self, requests):
        async def _send(to_send):
            await self._websocket.send(to_send)
        if type(requests) is not list:
            requests = [requests]
        for request in requests:
            self._record_request(request)
        if self.active:
            asyncio.run(_send(json.dumps({"requests": requests})))

    def basic_request(self, service: str, command: str, parameters: dict = None):
        if self._streamer_info is None:
            response = self._client.preferences()
            if response.ok:
                self._streamer_info = response.json().get('streamerInfo', None)[0]
            else:
                return {}
        if parameters is not None:
            for key in list(parameters.keys()):
                if parameters[key] is None:
                    del parameters[key]
        self._request_id += 1
        request = {
            "service": service.upper(),
            "command": command.upper(),
            "requestid": self._request_id,
            "SchwabClientCustomerId": self._streamer_info.get("schwabClientCustomerId"),
            "SchwabClientCorrelId": self._streamer_info.get("schwabClientCorrelId"),
        }
        if parameters is not None and len(parameters) > 0:
            request["parameters"] = parameters
        return request

    @staticmethod
    def _list_to_string(ls):
        if type(ls) is str: return ls
        elif type(ls) is list: return ",".join(map(str, ls))

    def level_one_futures(self, keys, fields, command="ADD"):
        return self.basic_request("LEVELONE_FUTURES", command,
                                  parameters={"keys": Stream._list_to_string(keys),
                                              "fields": Stream._list_to_string(fields)})

    def chart_futures(self, keys, fields, command="ADD"):
        return self.basic_request("CHART_FUTURES", command,
                                  parameters={"keys": Stream._list_to_string(keys),
                                              "fields": Stream._list_to_string(fields)})
