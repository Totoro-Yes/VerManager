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
import typing as Typ
from manager.master.postProc import PostProc
from manager.master.task import Task
from manager.master.exceptions import \
    POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY
from manager.basic.observer import Observer


async def postProcHandler(task: Task) -> None:
    task.job = "Result"


async def postProcHandler_acc(task: Task) -> None:
    if task.job is None:
        task.job = "R"
    else:
        task.job += "R"


class Listener(Observer):

    def __init__(self):
        Observer.__init__(self)
        self.result = None

    async def success(self, data: Typ.Any) -> None:
        self.result = True

    async def fail(self, data: Typ.Any) -> None:
        self.result = False


class PostProcTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = PostProc()

        # Listener Setup
        lis = self.lis = Listener()
        lis.handler_install(self.sut.NOTIFY_TAKS_FAIL, lis.fail)
        lis.handler_install(self.sut.NOTIFY_TASK_DONE, lis.success)

        self.sut.subscribe(self.sut.NOTIFY_TASK_DONE, lis)
        self.sut.subscribe(self.sut.NOTIFY_TAKS_FAIL, lis)

    async def test_PP_Create(self) -> None:
        self.assertIsNotNone(self.sut)

    async def test_PP_ProcTask__SingleProc_Success(self) -> None:
        """
        Process task with only one process
        """
        # Setup
        self.sut.addProc("key", postProcHandler)
        self.sut.start()

        # Exercise
        task = Task("ID", "SN", "VSN")
        self.sut.post_req(("key", task))
        await asyncio.sleep(1)

        # Verify
        self.assertEqual("Result", task.job)
        self.assertEqual(True, self.lis.result)

    async def test_PP_ProcTask__SingoleProc_Fail(self, ) -> None:
        """
        Process task with only one failed process
        """

    async def test_PP_ProcTask__MultiProc_Success(self) -> None:
        """
        Process task with multiple process
        """
        # Setup
        self.sut.addProc("Key", postProcHandler)
        self.sut.addProc("Key", postProcHandler)

        # Exercise
        task = Task("ID", "SN", "VSN")
        self.sut.post_req(("Key", task))
        await asyncio.sleep(1)

        # Verify
        self.assertEqual("RR", task.job)
        self.assertEqual(True, self.lis.result)

    async def test_PP_ProcTask__MultiProc_Fail(self) -> None:
        """
        Process task with multiple failed process
        """

    async def test_PP_GetHandler__NotExists(self) -> None:
        """
        Get handler which doesn't exists.
        """
        try:
            self.sut.getHandlers("Not Exists")
            self.fail("Handler is not exists")
        except POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY:
            self.assertTrue(True)

    async def test_PP_AddPostHandler(self) -> None:
        """
        Add a handler
        """
        self.sut.addProc("key", postProcHandler)

        handlers = self.sut.getHandlers("key")
        self.assertEqual(handlers, [postProcHandler])

    async def test_PP_AddPostHandler__Duplicate(self) -> None:
        """
        Add a handler with duplicate key
        """
        self.sut.addProc("key", postProcHandler)
        self.sut.addProc("key", postProcHandler)

        handlers = self.sut.getHandlers("key")
        self.assertEqual(handlers, [postProcHandler, postProcHandler])
