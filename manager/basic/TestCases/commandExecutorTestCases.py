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
import os
import psutil
import typing as T
from datetime import datetime
from manager.basic.commandExecutor import CommandExecutor


async def stopCE(ce: CommandExecutor) -> None:
    await asyncio.sleep(2)
    await ce.stop()


async def output_proc(data: bytes, *args) -> None:
    args[0].append(data.decode())


async def check_cmd_terminated(ce: CommandExecutor) -> None:
    while True:
        if ce.isRunning():
            pid = ce.pid()
            ps = psutil.Process(pid)

            children = ps.children(recursive=True)

            break
        else:
            await asyncio.sleep(0.1)
            continue

    await asyncio.sleep(3)

    for c in children:
        assert(c.is_running() is False)


class CommandExecutorTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = CommandExecutor()

    async def test_CE_NotrmalCommand(self) -> None:
        """
        CommandExecutor Run command
        """
        self.sut.setCommand(["echo ll > ./CET_TEST"])
        await self.sut.run()

        # Verify
        self.assertTrue(os.path.exists("./CET_TEST"))

        # Teardown
        os.remove("./CET_TEST")

    async def test_CE_StuckedCommand(self) -> None:
        """
        CommandExecutor run a command that stucked out of limit
        """
        self.sut.setCommand(["sleep 10"])
        self.sut.setStuckedLimit(1)

        before = datetime.now()
        await self.sut.run()
        after = datetime.now()

        # Verify
        self.assertLessEqual((after - before).seconds, 2)

    async def test_CE_TerminatedCommand(self) -> None:
        """
        CommandExecutor terminate command
        """
        self.sut.setCommand(["sleep 10"])

        await asyncio.gather(
            # Execute the command
            self.sut.run(),
            # Stop command after 2 seconds
            stopCE(self.sut),
            # To check that whether the command
            # is terminated
            check_cmd_terminated(self.sut)
        )

    async def test_CE_OutputProcess(self) -> None:
        """
        Process command output in realtime.
        """
        content = []  # type: T.List[str]
        self.sut.setCommand(["echo 123; echo 456"])
        self.sut.set_output_proc(output_proc, content)

        await self.sut.run()

        self.assertEqual(["123\n456\n"], content)
