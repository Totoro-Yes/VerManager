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
import manager.worker.TestCases.misc.linker as misc
import manager.worker.configs as cfg
import typing as T

from manager.basic.letter import Letter, NotifyLetter
from manager.basic.info import Info
from manager.worker.connector import Linker, Connector


class ServerProto(asyncio.DatagramProtocol):

    def __init__(self, dataBox: T.List) -> None:
        self.dataBox = dataBox

    def datagram_received(self, data: bytes, addr) -> None:
        self.dataBox.append(data.decode())


class ServerProto_LParse(asyncio.DatagramProtocol):

    def __init__(self, dataBox: T.List) -> None:
        self.dataBox = dataBox

    def datagram_received(self, data: bytes, addr) -> None:
        letter = Letter.parse(data)
        self.dataBox.append(letter)


class ClientProto(asyncio.DatagramProtocol):

    def datagram_received(self, data, addr) -> None:
        return


class ConnectorTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        cfg.config = Info("manager/worker/TestCases/misc/jobprocunit_config.yaml")
        self.connector = Connector()

    async def test_Connector_CreateEndpoint(self) -> None:
        # Setup
        dataBox = []  # type: T.List[str]

        transport, _ = await asyncio.get_running_loop()\
            .create_datagram_endpoint(
                lambda: ServerProto(dataBox),
                local_addr=("127.0.0.1", 3501)
            )

        # Exercise
        await self.connector.create_endpoint(
            "E1", ("127.0.0.1", 3501), proto=ClientProto())
        endpoint = self.connector.get_endpoint("E1")
        if endpoint is None:
            self.fail("endpoint is not created")

        endpoint.sendto(b"123456")  # type: ignore
        await asyncio.sleep(1)

        # Verify
        self.assertEqual(["123456"], dataBox)

    async def test_Connector_SendDatagramViaEndpoint(self) -> None:
        # Setup
        dataBox = []  # type: T.List[Letter]

        transport, _ = await asyncio.get_running_loop()\
            .create_datagram_endpoint(
                lambda: ServerProto_LParse(dataBox),
                local_addr=("127.0.0.1", 3501)
            )
        await self.connector.create_endpoint(
            "E1", ("127.0.0.1", 3501), proto=ClientProto()
        )

        # Exercise
        self.connector.sendDatagram_bytes(
            "E1", b"DATA",
            lambda data: NotifyLetter("A1", "TT", {"data": data.decode()}))
        await asyncio.sleep(1)

        # Verify
        self.assertEqual("DATA", dataBox[0].getContent('data'))


class LinkerTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        cfg.config = Info("manager/worker/TestCases/misc/jobprocunit_config.yaml")
        self.linker = Linker()

    async def test_Linker_NewLink_Connect(self) -> None:
        """
        Linker try to open a connection to VirtualServer.
        If success a link should be spawned.
        """
        # Setup
        vir_server = misc.VirtualServer("127.0.0.1", 8888)
        vir_server.start()
        await asyncio.sleep(0.1)

        # Exercise
        await self.linker.new_link("Server", "127.0.0.1", 8888)
        await asyncio.sleep(0.1)

        # Verify
        self.assertTrue(self.linker.exists("Server"))

    async def test_Linker_NewLink_Accept(self) -> None:
        """
        Linker listen on 8889 and VirtualWworker will
        connect to it. There should be a link exists.
        """

        # Setup
        vir_worker = misc.VirtualWorker("VirtualWorker", "127.0.0.1", 8889)

        # Exercise
        await self.linker.new_listen("lis1", "127.0.0.1", 8889)
        await asyncio.sleep(0.1)
        vir_worker.start()
        await asyncio.sleep(0.1)

        # Verify
        self.assertTrue(self.linker.exists("VirtualWorker"))

    async def test_Linker_Heartbeat_PASSIVE(self) -> None:
        """
        Maintain a link between a VirtualWorker and Linker
        """

        # Setup
        vir_worker = misc.VirtualWorker_Heartbeat_ACTIVE(
            "Worker", "127.0.0.1", 9000)

        # Exercise
        await self.linker.new_listen("lis1", "127.0.0.1", 9000)
        await asyncio.sleep(0.1)

        vir_worker.start()
        await asyncio.sleep(3)

        # Verify
        self.assertGreater(vir_worker._hbCount, 1)

    async def test_Linker_Heartbeat_Active(self) -> None:
        """ Maintain a linke of a passive """

        # Setup
        vir_worker = misc.VirtualWorker_Heartbeat_Passive("Worker",
                                                          "127.0.0.1", 8810)

        # Exercise
        vir_worker.start()
        await asyncio.sleep(3)

        self.linker._hostname = "abc"
        await self.linker.new_link("Worker", "127.0.0.1", 8810)
        await asyncio.sleep(0.1)

        # Verify
        self.assertGreater(vir_worker._hbCount, 0)

    async def test_Linker_Msg_Callback_Passive(self) -> None:
        """
        Linker send letter to outer world via message_callback
        """

        # Setup
        q = asyncio.Queue(10)  # type: asyncio.Queue
        self.linker.msg_callback = misc.msg_callback(self, q)
        vir_worker = misc.VirtualWorker_SendCommand("Worker", "127.0.0.1", 8811)

        # Exercise
        await self.linker.new_listen("lis1", "127.0.0.1", 8811)
        await asyncio.sleep(0.1)

        vir_worker.start()
        await asyncio.sleep(3)

        # Verify
        self.assertGreater(q.qsize(), 0)

    async def test_Linker_Active_Link_Rebuild(self) -> None:
        """ Link rebuild """

        # Setup
        vir_worker = misc.VirtualWorker_AutoDisconnect(
            "Worker", "127.0.0.1", 9999)

        # Exercise
        vir_worker.start()
        await asyncio.sleep(0.1)

        self.linker._hostname = "Name"
        await self.linker.new_link("lid", "127.0.0.1", 9999)
        await asyncio.sleep(10)

        # Verify
        self.assertGreater(vir_worker._reconn_count, 0)
