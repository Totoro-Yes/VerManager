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

import os
import unittest
import asyncio
import typing
import manager.worker.TestCases.misc.procunit as misc
import manager.worker.configs as configs

from datetime import datetime
from manager.basic.info import Info
from manager.basic.letter import CommandLetter, NewLetter,\
    BinaryLetter
from manager.worker.procUnit import ProcUnit, JobProcUnit,\
    PROC_UNIT_HIGHT_OVERLOAD, PROC_UNIT_IS_IN_DENY_MODE,\
    PostProcUnit, PostTaskLetter, UNIT_TYPE_JOB_PROC, Post,\
    CommandExecutor
from manager.worker.proc_common import Output
from manager.worker.channel import ChannelEntry


handled = False


async def handler(unit: ProcUnit, letter: CommandLetter) -> None:
    global handled

    type = letter.getType()
    if type == "H":
        handled = True


class ProcUnitMock(ProcUnit):

    def __init__(self, ident: str) -> None:
        ProcUnit.__init__(self, ident, UNIT_TYPE_JOB_PROC)

        self.procLogic = None  # type: typing.Any
        self.result = False
        self._stop = False
        self.channel_data = {}  # type: typing.Dict

    async def run(self) -> None:
        await self.procLogic(self)

    async def reset(self) -> None:
        return None

    async def cleanup(self) -> bool:
        return True


class ProcUnitUnitTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.pu = ProcUnitMock("Unit")

    async def test_ProcUnit_ProcLogic(self) -> None:
        # Setup
        self.pu.procLogic = misc.procUnitMock_Logic

        # Exercise
        self.pu.start()
        letter = CommandLetter("T", {})
        await self.pu.proc(letter)

        await asyncio.sleep(0.1)

        # Verify
        self.assertTrue(self.pu.result)
        self.assertEqual(ProcUnit.STATE_STOP, self.pu.state())

    async def test_ProcUnit_Stop(self) -> None:
        # Setup
        self.pu.procLogic = misc.procUnitMock_Logic

        # Exercise
        self.pu.start()
        self.pu.stop()

        # Verify
        self.assertEqual(ProcUnit.STATE_STOP, self.pu.state())

    async def test_ProcUnit_HightOverLoad(self) -> None:
        # Setup
        self.pu.procLogic = misc.procUnitMock_BlockTheQueue

        # Exercise
        self.pu.start()
        while True:
            try:
                await self.pu.proc(
                    CommandLetter("HIGH", {}))
            except PROC_UNIT_HIGHT_OVERLOAD:

                # Verify
                self.pu._stop = True
                self.assertTrue(ProcUnit.STATE_OVERLOAD, self.pu.state())
                self.assertTrue(self.pu._normal_space.qsize() >
                                self.pu._hightwaterlevel)
                return

        self.fail("No overload exception is raised")

    async def test_ProcUnit_DenyState(self) -> None:
        # Setup
        self.pu.procLogic = misc.procUnitMock_BlockTheQueue

        # Exercise
        self.pu.start()
        while True:
            try:
                await self.pu.proc(
                    CommandLetter("DENY", {}))
            except PROC_UNIT_HIGHT_OVERLOAD:
                pass
            except PROC_UNIT_IS_IN_DENY_MODE:
                # Verify
                self.pu._stop = True
                self.assertTrue(ProcUnit.STATE_DENY, self.pu.state())
                self.assertTrue(self.pu._normal_space.full())

                return

    async def test_ProcUnit_Output(self) -> None:
        # Setup
        output = Output()
        output.setConnector(misc.Connector())
        self.pu.procLogic = misc.logic_send_packet
        self.pu.setOutput(output)

        # Exercise
        output.ready()
        self.pu.start()
        await asyncio.sleep(0.1)

        # Verify
        try:
            letter = self.pu._output_space._connector.q.get_nowait()  # type: ignore
            typ = letter.getType()

            self.assertEqual("Reply", typ)

            success = True
        except asyncio.QueueEmpty:
            success = False

        self.assertTrue(success)


class JobProcUnitTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        configs.config = Info("manager/worker/TestCases/misc/jobprocunit_config.yaml")

        self.sut = JobProcUnit("JobUnit")
        self.queue = asyncio.Queue(10)  # type: asyncio.Queue

        output = Output()
        self.connector = misc.Connector()
        output.setConnector(self.connector)
        self.sut.setOutput(output)

        self.sut.setChannel(ChannelEntry("JobProcUnit"))

    async def test_JobProcUnit_JobProc(self) -> None:
        # Setup
        self.sut.start()

        # Exercise
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["echo Doing...", "echo job > job_result"],
                         'resultPath': "./job_result",
                         'PostTarget': '1'})
        await self.sut._normal_space.put(job)

        # Verify
        while True:
            letter = await asyncio.wait_for(self.connector.q.get(), timeout=5)

            if not isinstance(letter, BinaryLetter):
                continue

            self.assertEqual(b'job\n', letter.getContent('bytes'))
            break

    async def test_JobProcUnit_Exists(self) -> None:
        # Setup
        self.sut.start()

        # Exercise
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["echo job > job_result", "echo 123"],
                         'resultPath': "./job_result"})
        job1 = NewLetter("Job1", "123456", "v1", "",
                         {'cmds': ["sleep 10", "echo job > job_result"],
                          'resultPath': "./job_result"})
        job2 = NewLetter("Job2", "123456", "v1", "",
                         {'cmds': ["sleep 10", "echo job > job_result"],
                          'resultPath': "./job_result"})

        await self.sut._normal_space.put(job)
        await self.sut._normal_space.put(job1)
        await self.sut._normal_space.put(job2)
        await asyncio.sleep(1)

        # Verify
        self.assertTrue(self.sut.exists("Job"))
        self.assertTrue(self.sut.exists("Job1"))
        self.assertTrue(self.sut.exists("Job2"))

    async def test_JobProcUnit_Cancel(self) -> None:
        # Setup
        self.sut.start()

        # Exercise
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["sleep 100", "echo job > job_result"],
                         'resultPath': "./job_result",
                         'PostTarget': '1'})

        await self.sut._normal_space.put(job)
        await asyncio.sleep(3)

        await self.sut.cancel("Job")

        self.assertFalse(self.sut.exists("Job"))

    async def test_JobProcUnit_CancelInQueue(self) -> None:
        # Setup
        self.sut.start()

        # Exercise
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["sleep 10", "echo job > job_result"],
                         'resultPath': "./job_result"})
        job1 = NewLetter("Job1", "123456", "v1", "",
                         {'cmds': ["sleep 10", "echo job > job_result"],
                          'resultPath': "./job_result"})
        job2 = NewLetter("Job2", "123456", "v1", "",
                         {'cmds': ["sleep 10", "echo job > job_result"],
                          'resultPath': "./job_result"})

        await self.sut._normal_space.put(job)
        await self.sut._normal_space.put(job1)
        await self.sut._normal_space.put(job2)
        await asyncio.sleep(3)

        # Cancel
        await self.sut.cancel("Job1")

        # Verify
        self.assertTrue(self.sut.exists("Job"))
        self.assertTrue(self.sut.exists("Job2"))
        self.assertFalse(self.sut.exists("Job1"))

    @unittest.skip("Temporary")
    async def test_JobProcUnit_CommandLog(self) -> None:
        # Setup
        self.sut.start()

        # Exercise
        job = NewLetter("Job", "123456", "v1", "",
                        {'cmds': ["echo 123"],
                         'resultPath': "./job_result"})

        await self.sut._normal_space.put(job)
        await asyncio.sleep(1)

        # Verify
        dataes = self.connector.dataes
        self.assertTrue(len(dataes) == 1)
        self.assertEqual("123\n", dataes[0].getContent("message"))


class PostProcUnitTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        configs.config = Info("manager/worker/TestCases/misc/jobprocunit_config.yaml")
        self.sut = PostProcUnit("PostProcUnit")
        self.queue = asyncio.Queue(10)  # type: asyncio.Queue

        output = Output()
        self.connector = misc.Connector()
        output.setConnector(self.connector)
        self.sut.setOutput(output)

        self.sut.setChannel(ChannelEntry("JobProcUnit"))

    @unittest.skip("PostProcUnit will cleanup before verify")
    async def test_PostProcUnit_Do(self) -> None:
        # Setup
        self.sut.start()

        # Exercise

        # Put a PostTaskLetter
        await self.sut._normal_space.put(
            PostTaskLetter("Version_123456", "Version",
                           ["cat file1 file2 > file3"],
                           "file3",
                           ["Version_file1", "Version_file2"])
        )

        # Transfer file1 to PostProcUnit
        await self.sut._normal_space.put(
            BinaryLetter("Version_file1", b"file1",
                         parent="Version", fileName="file1")
        )
        await self.sut._normal_space.put(
            BinaryLetter("Version_file1", b"",
                         parent="Version", fileName="file1")
        )

        # Transfer file2 to PostProcUnit
        await self.sut._normal_space.put(
            BinaryLetter("Version_file2", b"file2",
                         parent="Version", fileName="file2")
        )
        await self.sut._normal_space.put(
            BinaryLetter("Version_file2", b"",
                         parent="Version", fileName="file2")
        )

        await asyncio.sleep(3)

        # Verify
        self.assertTrue(os.path.exists("./Post/Version/file3"))

    async def test_PostProcUnit_PostStop(self) -> None:
        """
        Start a post and then stop it
        after that Post should not in work.
        """

        # Setup
        post = Post("P", [""], ["sleep 10"], "/", "")
        if not os.path.exists("Post"):
            os.mkdir("Post")

        # Exercise
        asyncio.get_running_loop().create_task(post.do())
        await asyncio.sleep(1)
        await post.stop()

        # Verify
        self.assertFalse(post.isInWork())

    async def test_CommandExecutor_NormalCommand(self) -> None:
        """
        Run a normal,non-stucked command.
        """

        # Setup
        cmd = CommandExecutor(["echo ll > CommandExecutor"])

        # Exercise
        await cmd.run()

        # Verify
        self.assertTrue(os.path.exists("CommandExecutor"))
        self.assertFalse(cmd.isRunning())

        # Teardown
        os.remove("CommandExecutor")

    async def test_CommandExecutor_StuckedCommand(self) -> None:
        """
        Run a command that will stucked a long time.
        """

        # Setup
        cmd = CommandExecutor(["echo Hello", "sleep 20"])
        cmd.setStuckedLimit(5)

        # Exercise
        before = datetime.utcnow()
        await cmd.run()
        after = datetime.utcnow()

        # Verify
        self.assertEqual(-1, cmd.return_code())
        self.assertLessEqual((after-before).seconds, 12)
