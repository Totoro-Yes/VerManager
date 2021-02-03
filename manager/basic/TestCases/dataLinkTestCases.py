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
import unittest
import asyncio
from manager.basic.dataLink import DataLinker, DataLink, DataLinkNotify
from manager.basic.letter import sending, NotifyLetter


async def data_processor(dl: DataLink, data: typing.Any, args: typing.Any) -> None:
    received_data = args
    n = int(data.getHeader('ident'))
    received_data.append(n)

    if n == 9:
        notify = DataLinkNotify("Data", "SendDone")
        dl.notify(notify)


def data_processor_udp(dl: DataLink, data: typing.Any, args: typing.Any) -> None:
    received_data = args
    n = int(data.getHeader('ident'))
    received_data.append(n)

    if n == 9:
        notify = DataLinkNotify("Data", "SendDone")
        dl.notify(notify)



class ClientProtocol(asyncio.BaseProtocol):

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport


class DataLinkerTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.dlinker = DataLinker()

    async def test_DataLinker_TCP_ProcessData(self) -> None:
        # Setup
        received_data = []  # type: typing.List
        notify_content = []  # type: typing.List

        # Register Processor
        self.dlinker.addDataLink("127.0.0.1", 3500, DataLink.TCP_DATALINK,
                                 # Processor
                                 data_processor,
                                 # Processor args
                                 received_data)
        self.dlinker.addNotify("Data", lambda msg, arg: notify_content.append(msg), None)

        # Exercise
        self.dlinker.start()
        await asyncio.sleep(1)

        r, w = await asyncio.open_connection("127.0.0.1", 3500)

        n = 0

        while n < 10:
            letter = NotifyLetter(str(n), str(n), {})
            await sending(w, letter)
            await w.drain()
            n += 1
        await asyncio.sleep(1)

        # Verify
        self.assertEqual(["SendDone"], notify_content)

        self.dlinker.stop()

    async def test_DataLinker_UDP_ProcessData(self) -> None:
        # Setup
        received_data = []  # type: typing.List
        notify_content = []  # type: typing.List

        # Register Processor
        self.dlinker.addDataLink("127.0.0.1", 3501, DataLink.UDP_DATALINK,
                                 # Processor
                                 data_processor_udp,
                                 # Processor args
                                 received_data)
        self.dlinker.addNotify("Data", lambda msg, arg: notify_content.append(msg), None)

        transport, protocol = await asyncio.get_running_loop()\
            .create_datagram_endpoint(lambda: ClientProtocol(), remote_addr=('127.0.0.1', 3501))

        # Exercise
        self.dlinker.start()
        await asyncio.sleep(1)

        n = 0

        while n < 10:
            letter = NotifyLetter(str(n), str(n), {})
            transport.sendto(letter.toBytesWithLength())
            n += 1

        await asyncio.sleep(1)

        # Verify
        self.assertEqual(["SendDone"], notify_content)

        self.dlinker.stop()
