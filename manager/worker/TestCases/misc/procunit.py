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

import asyncio
import typing

from manager.basic.letter import CommandLetter, Letter, NewLetter, BinaryLetter
from manager.worker.procUnit import ProcUnit, JobProcUnit


# Things that used by ProcUnitTestCases
channel_data = {}  # type: typing.Dict


async def procUnitMock_Logic(p):

    try:
        letter = await p.job_retrive(timeout=1)
    except asyncio.exceptions.TimeoutError:
        return None

    if not isinstance(letter, CommandLetter):
        return None

    type = letter.getType()

    if type == "T":
        p.result = True
    else:
        p.result = False


async def procUnitMock_BlockTheQueue(unit):

    while True:
        await asyncio.sleep(1)


async def procUnitMock_NotifyChannel(unit: ProcUnit):
    unit._notify()


async def logic_send_packet(unit: ProcUnit):
    output = unit._output_space
    if output is None:
        return

    await output.send(CommandLetter("Reply", {}), timeout=0)


class Endpoint(asyncio.DatagramTransport):

    datas = []  # type: typing.List[str]

    def sendto(self, data, addr=None) -> None:
        Endpoint.datas.append(Letter.parse(data))


class DefautlDatagramProtocol(asyncio.DatagramProtocol):

    def datagram_received(self, data, addr) -> None:
        """
        Do nothing
        """
        return


class Connector:

    dataes = []  # type: typing.List

    def __init__(self) -> None:
        self.q = asyncio.Queue(10)  # type: asyncio.Queue

    async def sendLetter(self, letter: Letter, timeout=None) -> None:
        await self.q.put(letter)

    async def create_endpoint(
            self, endpoint_id: str,
            remote_address: typing.Tuple[str, int],
            proto: asyncio.DatagramProtocol = DefautlDatagramProtocol()) -> None:
        return

    def get_endpoint(self, eid: str) -> typing.Any:
        e = Endpoint()
        self.dataes = e.datas
        return e

    def shutdown_endpoint(self, eid: str) -> None:
        return None

    async def sendFile(self, linkid: str, tid: str, path: str,
                       version: str, fileName: str) -> bool:
        f = open(path, "rb")

        for line in f:
            bLetter = BinaryLetter(
                tid=tid, bStr=line,
                parent=version, fileName=fileName)
            await self.q.put(bLetter)

        f.close()

        return True


class ProcUnitStub_Dirty(ProcUnit):

    def __init__(self, ident: str, type_: str) -> None:
        ProcUnit.__init__(self, ident, type_)
        self.counter = 0

    async def cleanup(self) -> bool:
        self.counter += 1

        if self.counter == 1:
            return False
        else:
            return True

    async def run(self) -> None:
        self._state = ProcUnit.STATE_DIRTY
        self.msg_gen()
        await self._notify()

        while True:
            await asyncio.sleep(10)

    async def reset(self) -> None:
        return None


class JobProcUnit_CleanupFailed(JobProcUnit):

    async def cleanup(self) -> bool:
        return False

    async def _do_job(self, job: NewLetter) -> None:
        assert(self._channel is not None)
        self._state = JobProcUnit.STATE_DIRTY
        await self._channel.update_and_notify('state', self._state)
