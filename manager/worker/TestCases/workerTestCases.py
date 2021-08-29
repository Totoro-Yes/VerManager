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
import unittest
import typing

from manager.basic.letter import sending, receving, HeartbeatLetter, \
    PropLetter, ResponseLetter, BinaryLetter, NewLetter, Letter
from manager.worker.worker import Worker
from manager.basic.virtuals.virtualServer import VirtualServer
from manager.worker.TestCases.misc.procunit import JobProcUnit_CleanupFailed
from manager.worker.channel import ChannelEntry
from manager.worker.processor_comps import UnitMaintainer
from manager.worker.monitor import Monitor
from manager.worker.TestCases.misc.connector import ConnectorFake


class VirtualServer_Minimal(VirtualServer):

    async def sendToWorker(self, letter: Letter) -> None:
        await sending(self.w, letter)

    async def conn_callback(self,
                            r: asyncio.StreamReader,
                            w: asyncio.StreamWriter) -> None:
        """ HeartBeat """
        self._propc = 0
        self._hbc = 0
        self._responsec = 0
        self._binc = 0

        self.r = r
        self.w = w

        while True:
            letter = await receving(r)

            if isinstance(letter, PropLetter):
                self._propc += 1

            if isinstance(letter, HeartbeatLetter):
                letter.setHeader('ident', 'Master')
                await sending(w, letter)
                self._hbc += 1

            if isinstance(letter, ResponseLetter):
                self._responsec += 1

            if isinstance(letter, BinaryLetter):
                self._binc += 1


class WorkerTestCases_(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = Worker("./manager/misc/worker_test_configs/config.yaml")

    @unittest.skip("")
    async def test_Worker_Connect(self, ) -> None:
        # Setup
        vir_server = VirtualServer_Minimal("Master", "127.0.0.1", 30000)

        # Exercise
        vir_server.start()
        await asyncio.sleep(0.1)

        self.sut.start_nowait()
        await asyncio.sleep(3)

        # Verify
        self.assertEqual(vir_server._propc, 1)
        self.assertGreater(vir_server._hbc, 0)

    @unittest.skip("")
    async def test_worker_DoTask(self) -> None:
        # Setup
        vir_server = VirtualServer_Minimal("Master", "127.0.0.1", 30000)

        # Exercise
        vir_server.start()
        await asyncio.sleep(0.1)

        self.sut.start_nowait()
        await asyncio.sleep(0.1)

        # Send Task
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["echo Doing...", "echo job > job_result"],
                         'resultPath': "./job_result"})
        await vir_server.sendToWorker(job)
        await asyncio.sleep(10)

        # verify
        self.assertEqual(vir_server._responsec, 2)
        self.assertEqual(vir_server._binc, 2)

    async def test_Worker_JobProcUnitNotify(self) -> None:
        """
        This test is to asure that ProcUnit's state can
        send to Monitor via UnitMaintainer.
        """

        # Setup

        # Create a JobProcUnit
        unit = JobProcUnit_CleanupFailed("UNIT")
        unit._channel = ChannelEntry("UNIT")

        # Create UnitMaintainer
        units = {"UNIT": unit}  # type: typing.Dict
        um = UnitMaintainer(units)

        # Build a channel
        unit._channel.addReceiver(um)
        um.addTrack("UNIT", unit._channel.info)

        # Build Connector
        conn = ConnectorFake()

        # Create Monitor
        monitor = Monitor("W")
        monitor.setupConnector(conn)
        monitor.track(um)

        # Exercise
        monitor.start()
        um.start()
        await asyncio.sleep(0.1)

        await unit._do_job(None)
        await asyncio.sleep(0.1)

        # Verify
        self.assertTrue(len(conn.notifies) == 1)
