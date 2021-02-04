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

import abc
import asyncio
import typing

from manager.worker.connector import Connector
from manager.basic.letter import Letter


class Output:

    # Able to transfer data
    STATE_READY = 0

    # Unable to transfer data but
    # ProcUnit can still put data into
    # output space until out of space
    STATE_STOP = 1

    def __init__(self) -> None:
        self._connector = None  # type: typing.Optional[Connector]
        self._outputQ = None  # type: typing.Optional[asyncio.Queue]
        self._state = self.STATE_READY

        self._entities = {}  # type: typing.Dict[str, typing.Any]

    def addEntity(self, eid: str, entity: typing.Any) -> None:
        if eid in self._entities:
            return None
        self._entities[eid] = entity

    def rmEntity(self, eid: str) -> None:
        if eid not in self._entities:
            return None
        del self._entities[eid]

    def call(self, eid: str, proc: str, *args) -> typing.Any:
        f = self._get_entity_prop(eid, proc)
        if f is None:
            return None
        else:
            return f(*args)

    async def async_call(self, eid: str, proc: str, *args) -> typing.Any:
        f = self._get_entity_prop(eid, proc)
        if f is None:
            return None
        else:
            return await f(*args)

    def _get_entity_prop(self, eid: str, proc: str) -> typing.Any:
        if eid not in self._entities:
            return None

        entity = self._entities[eid]
        return getattr(entity, proc)

    def state(self) -> int:
        return self._state

    def ready(self) -> None:
        self._state = self.STATE_READY

    def stop(self) -> None:
        self._state = self.STATE_STOP

    def setState(self, state: int) -> None:
        self._state = state

    def setConnector(self, conn: Connector) -> None:
        self._entities['conn'] = conn
        self._connector = conn

    async def send(self, letter: Letter, timeout=None) -> None:
        assert(self._connector is not None)
        await self._connector.sendLetter(letter, timeout=timeout)

    async def sendfile(self, linkid: str, path: str,
                       tid: str, version: str, fileName: str) -> bool:
        assert(self._connector is not None)
        return await self._connector.sendFile(
            linkid, tid, path, version, fileName)

    def isReady(self) -> bool:
        return self._state == self.STATE_READY

    def isStop(self) -> bool:
        return self._state == self.STATE_STOP

    def link_state(self, linkid: str) -> int:
        assert(self._connector is not None)
        return self._connector.link_state(linkid)


class PROCESSOR_UNIT_ALREADY_EXISTS(Exception):

    def __init__(self, uid: str) -> None:
        self.uid = uid

    def __str__(self) -> str:
        return "Unit " + self.uid + " is alread installed"


class PROCESSOR_DISPATCHE_CANT_FIND_THE_TYPE(Exception):

    def __init__(self, type: str) -> None:
        self.type = type

    def __str__(self) -> str:
        return "Dispatcher can't find a unit to process type: " + self.type


class PROCESSOR_OUTPUT_STOP(Exception):
    pass
