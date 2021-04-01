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
    POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY,\
    POSTPROC_INVALID_REQUEST, \
    POSTPROC_NO_MORE_SPACE
from manager.basic.observer import Observer


async def postProcHandler(task: Task, arg: Typ.Any) -> None:
    task.job = "Result"


async def postProcHandler_acc(task: Task, arg: Typ.Any) -> None:
    if task.job is None:
        task.job = "R"
    else:
        task.job += "R"


async def postProcHandler_Fail(task: Task, arg: Typ.Any) -> None:
    raise Exception


class Listener(Observer):

    def __init__(self):
        Observer.__init__(self)
        self.result = None
        self.total = []  # type: Typ.List[Typ.Any]

    async def post_done_handle(self, data: Typ.Any) -> None:
        self.result = data
        self.total.append(data)


class PostProcTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = PostProc()

        # Listener Setup
        lis = self.lis = Listener()
        lis.handler_install(self.sut.NAME, lis.post_done_handle)
        self.sut.subscribe(self.sut.NOTIFY_TASK_DONE, lis)

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
        self.sut.post_req(("key", task, None))
        await asyncio.sleep(0.1)

        # Verify
        self.assertEqual("Result", task.job)
        self.assertEqual((True, "ID"), self.lis.result)

    async def test_PP_ProcTask__SingoleProc_Fail(self, ) -> None:
        """
        Process task with only one failed process
        """
        # Setup
        self.sut.addProc("Key", postProcHandler_Fail)
        self.sut.start()

        # Exercise
        task = Task("ID", "SN", "VSN")
        self.sut.post_req(("Key", task, None))
        await asyncio.sleep(0.1)

        # Verify
        self.assertEqual((False, "ID"), self.lis.result)

    async def test_PP_ProcTask__MultiProc_Success(self) -> None:
        """
        Process task with multiple process
        """
        # Setup
        self.sut.addProc("Key", postProcHandler_acc)
        self.sut.addProc("Key", postProcHandler_acc)
        self.sut.start()

        # Exercise
        task = Task("ID", "SN", "VSN")
        self.sut.post_req(("Key", task, None))
        await asyncio.sleep(0.1)

        # Verify
        self.assertEqual("RR", task.job)
        self.assertEqual((True, "ID"), self.lis.result)

    async def test_PP_ProcTask__MultiProc_Fail(self) -> None:
        """
        Process task with multiple failed process
        """
        # Setup
        self.sut.addProc("Key", postProcHandler_acc)
        self.sut.addProc("Key", postProcHandler_Fail)
        self.sut.addProc("Key", postProcHandler_acc)
        self.sut.start()

        # Exercise
        task = Task("ID", "SN", "VSN")
        self.sut.post_req(("Key", task, None))
        await asyncio.sleep(0.1)

        # Verify
        self.assertEqual("R", task.job)
        self.assertEqual((False, "ID"), self.lis.result)

    async def test_PP_ProcTask__MultiTask_All_Success(self, ) -> None:
        """
        Process tasks that all success.
        """
        # Setup

        # Task 1
        self.sut.addProc("key1", postProcHandler_acc)
        self.sut.addProc("key1", postProcHandler_acc)

        # Task 2
        self.sut.addProc("key2", postProcHandler_acc)
        self.sut.addProc("key2", postProcHandler_acc)

        # Task 3
        self.sut.addProc("key3", postProcHandler_acc)
        self.sut.addProc("key3", postProcHandler_acc)

        self.sut.start()

        # Exercise
        t1 = Task("ID1", "SN", "VSN")
        t2 = Task("ID2", "SN", "VSN")
        t3 = Task("ID3", "SN", "VSN")
        for req in [("key1", t1, None), ("key2", t2, None), ("key3", t3, None)]:
            self.sut.post_req(req)

        await asyncio.sleep(1)

        # Veirfy
        self.assertEqual([(True, "ID1"), (True, "ID2"), (True, "ID3")], self.lis.total)
        self.assertEqual("RR", t1.job)
        self.assertEqual("RR", t2.job)
        self.assertEqual("RR", t3.job)

    async def test_PP_ProcTask__InvalidInput(self) -> None:
        """
        Request with invalid data type.
        """
        try:
            self.sut.post_req("123")
            self.fail("Invalid req should not passed")
        except POSTPROC_INVALID_REQUEST:
            pass

        try:
            task = Task("ID1", "SN", "VSN")
            self.sut.post_req((123, task))
            self.fail("Invalid req should not passed")
        except POSTPROC_INVALID_REQUEST:
            pass

        try:
            self.sut.post_req(("123", "132"))
            self.fail("Invalid req should not passed")
        except POSTPROC_INVALID_REQUEST:
            pass

        task = Task("ID1", "SN", "VSN")
        try:
            self.sut.post_req(("123", task, None))
            self.fail("Invalid req should not passed")
        except POSTPROC_INVALID_REQUEST:
            pass
        except POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY:
            pass

        self.sut.addProc("123", postProcHandler)
        self.sut.post_req(("123", task, None))

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

    async def test_PP_Requst__QueueFull(self) -> None:
        """
        Request to PostPorc after request queue is full.
        """
        task = Task("ID", "SN", "VSN")
        self.sut.addProc("key", postProcHandler)

        try:
            i = 0
            while i < 200:
                self.sut.post_req(("key", task, None))
                i += 1
        except POSTPROC_NO_MORE_SPACE:
            return

        self.fail("Queue full")
