# MIT License
#
# Copyright (c) 2020 Gcom
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import typing
import client.client as client
from channels.generic.websocket import AsyncWebsocketConsumer
from client.models import Clients
from typing import Dict, Any
from channels.db import database_sync_to_async
from channels.exceptions import AcceptConnection
from client.messages import ClientEvent
from client.clientEventProcessor import ClientEventProcessor
from client.exceptions import FAILED_TO_QUERY


class CommuConsumer(AsyncWebsocketConsumer):

    async def connect(self) -> None:
        # Use channel name as a client
        # so another app can use this consumer
        # to communicate with client
        await client_create(self.channel_name)
        client.clients[self.channel_name] = \
            client.Client(self.channel_name)

        # Accept connection
        raise AcceptConnection

    async def disconnect(self, close_code) -> None:
        await client_delete(self.channel_name)
        del client.clients[self.channel_name]

    async def server_message(self, event: Dict[str, Any]) -> None:
        # Message from server to client.
        await self.send(str(event['message']))

    async def receive(self, text_data=None, bytes_data=None) -> None:
        """
        Client will send datas in json format. These datas will
        convert into Message
        """

        try:
            event = ClientEvent(text_data)
            replies = await ClientEventProcessor.proc(event)
            if replies is None:
                raise FAILED_TO_QUERY()

            for reply in replies:
                await self.send(str(reply))

        except FAILED_TO_QUERY:
            pass
        except Exception:
            # Need to be logged
            import traceback
            traceback.print_exc()

    async def job_msg(self, event: typing.Dict) -> None:
        await self.send(event['text'])

    async def job_msg_history(self, event: typing.Dict) -> None:
        await self.send(event['text'])

    async def job_msg_file_new(self, event: typing.Dict) -> None:
        await self.send(event['text'])

    async def job_msg_task_output(self, event: typing.Dict) -> None:
        await self.send(event['text'])


async def client_create(name: str) -> None:
    # Store Client's name into database
    # calling when a client is connected
    await database_sync_to_async(
        Clients.objects.create
    )(client_name=name)


async def client_delete(name: str) -> None:
    # Delete client's name from database
    # calling when a client is disconnected
    client = await database_sync_to_async(
        Clients.objects.filter
    )(client_name=name)

    await database_sync_to_async(
        client.delete
    )()
