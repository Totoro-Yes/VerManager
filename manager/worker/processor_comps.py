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

from manager.worker.channel import ChannelBox
from manager.worker.procUnit import \
    ProcUnit, PROC_UNIT_HIGHT_OVERLOAD, PROC_UNIT_IS_IN_DENY_MODE
from manager.basic.letter import Letter
from manager.worker.proc_common import \
    PROCESSOR_DISPATCHE_CANT_FIND_THE_TYPE
from manager.worker.channel import ChannelReceiver
from manager.worker.monitor import StateObject
from manager.basic.mmanager import Daemon


class Dispatcher:

    def __init__(self) -> None:
        self._units = {}  # type: typing.Dict[str, ProcUnit]

    def addUnit(self, type: str, unit: ProcUnit) -> None:
        if type in self._units:
            return None
        self._units[type] = unit

    async def dispatch(self, cl: Letter) -> None:
        type_ = cl.typeOfLetter()  # type: ignore

        if type_ not in self._units:
            raise PROCESSOR_DISPATCHE_CANT_FIND_THE_TYPE(type_)

        # These two exception will be dealt by UnitMaintainer.
        # Dispatcher is focus on work of dispatch.
        try:
            await self._units[type_].proc(cl)
        except (PROC_UNIT_HIGHT_OVERLOAD, PROC_UNIT_IS_IN_DENY_MODE) as e:
            print(e)


class UnitMaintainer(Daemon, ChannelReceiver, StateObject):

    def __init__(self, ucontainer: typing.Dict[str, ProcUnit]) -> None:
        StateObject.__init__(self, "UM")
        Daemon.__init__(self)
        ChannelReceiver.__init__(self)

        self._units = ucontainer
        self._restart_delay = 10
        self._event = asyncio.Event()

    async def update(self, uid: str) -> None:
        info = self.last(uid)
        if info is None:
            return None
        await self._maintain(uid, info)

    def setRestartDelay(self, delay: int) -> None:
        self._restart_delay = delay

    async def _maintain(self, uid: str, info: typing.Dict) -> None:
        state = int(info['state'])

        if state == ProcUnit.STATE_DENY or \
           state == ProcUnit.STATE_STOP or \
           state == ProcUnit.STATE_DIRTY:

            try:
                # Notify to Monitor
                # Processor is not ready to accept a job
                await self.pending()

                # Set the event so UnitMaintainer
                # will try to correct the problems.
                if not self._event.is_set():
                    self._event.set()
            except Exception as e:
                # Need to log
                pass

    async def run(self) -> None:

        while True:

            ret = True

        # Wait event
            # This event will be seted
            # if a unit is need help
            await self._event.wait()

            for unit in self._units.values():
                if unit.state() == ProcUnit.STATE_DIRTY:
                    if await unit.cleanup() is True:
                        unit.setState(ProcUnit.STATE_READY)
                    else:
                        ret = False

            # All problems is resolved.
            if ret is True:
                await self.ready()
                self._event.clear()
            else:
                await asyncio.sleep(5)

    @staticmethod
    async def unitRestart(unit: ProcUnit) -> None:
        # Prevent exhaust resources in some cases
        await asyncio.sleep(10)
        unit.start()
