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
import asyncio

from manager.worker.procUnit import ProcUnit, \
    JobProcUnitProto, PostProcUnitProto
from manager.basic.mmanager import ModuleDaemon
from manager.basic.letter import Letter, CommandLetter, BinaryLetter
from manager.worker.processor_comps import Dispatcher, UnitMaintainer
from manager.worker.proc_common import Output,\
    PROCESSOR_UNIT_ALREADY_EXISTS
from manager.worker.connector import Connector
from manager.worker.channel import Channel, ChannelReceiver


class Processor(ModuleDaemon):

    NAME = "Processor"
    CMDHandler = typing.Callable[[CommandLetter], typing.Coroutine]

    def __init__(self) -> None:
        ModuleDaemon.__init__(self, self.NAME)

        self._unit_container = {}  # type: typing.Dict[str, ProcUnit]
        self._maintainer = UnitMaintainer(self._unit_container)
        self._channel = Channel()
        self._t = None  # type: typing.Optional[asyncio.Task]
        self._dispatcher = Dispatcher()
        self._reqQ = asyncio.Queue(4096)  # type: asyncio.Queue[Letter]
        self._output = Output()

    async def begin(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    def setup_output(self, conn: Connector) -> None:
        self._output.setConnector(conn)

    def req(self, letter: Letter) -> None:
        self._reqQ.put_nowait(letter)

    def getMaintainer(self) -> UnitMaintainer:
        return self._maintainer

    def install_unit(self, unit: ProcUnit) -> None:
        uid = unit.ident()
        if uid in self._unit_container:
            raise PROCESSOR_UNIT_ALREADY_EXISTS(uid)
        self._unit_container[uid] = unit

        # Setup channel for unit and add
        # UnitMaintainer as a receiver of this
        # ProcUnit
        channel = self._channel.addChannel(uid)
        unit.setChannel(channel)
        unit.msg_gen()

        # UnitMaintainer need info of Unit
        # to make sure the ProcUnit is Health.
        self.register(uid, self._maintainer)

        # Setup output space for unit
        unit.setOutput(self._output)

    def set_type_dispatch_to_unit(self, type: str, uid: str) -> None:
        if uid not in self._unit_container:
            raise UNIT_NOT_FOUND(uid)

        unit = self._unit_container[uid]
        self._dispatcher.addUnit(type, unit)

    async def run(self) -> None:

        # Start UnitMaintainer
        self._maintainer.start()

        # Start all ProcUnit
        for unit in self._unit_container.values():
            unit.start()

        while True:
            letter = await self._reqQ.get()

            # Deal with CommandLetter
            if isinstance(letter, CommandLetter):
                await self.CMD_Proc(letter)
            else:
                # If not a CommandLetter then dispatch to
                # ProcUnit
                await self._dispatcher.dispatch(letter)

    def register(self, uid: str, comp: ChannelReceiver) -> None:
        if self._channel.isChannelExists(uid):
            self._channel.addReceiver(uid, comp)

    def unitInfo(self, uid: str) -> typing.Optional[typing.Dict]:
        return self._channel.getChannelData(uid)

    #################################################
    # Section of methods that for command deal with #
    #################################################
    async def CMD_Proc(self, cl: CommandLetter) -> None:
        """ Command process entry """
        type = cl.getType().upper()

        h = self.CMD_SEARCH_HANDLER(type)
        if h is None:
            return None

        await h(cl)

    def CMD_SEARCH_HANDLER(self, type) -> typing.Optional[typing.Callable]:
        try:
            return getattr(self, 'CMD_H_'+type)
        except AttributeError:
            return None

    async def CMD_H_ACCEPT(self, cl: CommandLetter) -> None:
        """ Master is accept this worker """
        self._output.ready()

    async def CMD_H_ACCEPT_RST(self, cl: CommandLetter) -> None:
        """
        Reset all ProcUnit's status before it's begin to
        process any jobs from master.
        """
        for unit in self._unit_container.values():
            await unit.reset()
        self._output.ready()

    async def CMD_H_CANCEL_JOB(self, cl: CommandLetter) -> None:

        tid = cl.getTarget()

        for unit in self._unit_container.values():
            if isinstance(unit, JobProcUnitProto):
                jobUnit = typing.cast(JobProcUnitProto, unit)

                if jobUnit.exists(tid):
                    await jobUnit.cancel(tid)

            elif isinstance(unit, PostProcUnitProto):
                postUnit = typing.cast(PostProcUnitProto, unit)

                if postUnit.exists(tid):
                    await postUnit.cancel(tid)


class UNIT_NOT_FOUND(Exception):

    def __init__(self, uid: str) -> None:
        self._uid = uid

    def __str__(self) -> str:
        return "Unit " + self._uid + " is not found in Processor."
