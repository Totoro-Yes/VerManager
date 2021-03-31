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
import typing as Typ
from manager.basic.mmanager import ModuleDaemon
from manager.basic.observer import Subject
from manager.master.task import Task
from manager.master.exceptions import POSTPROC_NO_MORE_SPACE, \
    POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY
from manager.basic.util import loop_forever_async

PostHandler = Typ.Callable[[Task], Typ.Coroutine]
PostProcReq = Typ.Tuple[str, Task]


class PostProc(ModuleDaemon, Subject):

    NAME = "PostProc"
    NOTIFY_TASK_DONE = "DONE"
    NOTIFY_TAKS_FAIL = "FAIL"

    def __init__(self) -> None:
        ModuleDaemon.__init__(self, self.NAME)

        # Subject Init
        Subject.__init__(self, self.NAME)
        self.addType(self.NOTIFY_TASK_DONE)
        self.addType(self.NOTIFY_TAKS_FAIL)

        # Queue of tasks, which need to be
        # processed.
        self._reqs = asyncio.Queue(100)  # type: asyncio.Queue[PostProcReq]

        self._handlers = {}  # type: Typ.Dict[str, Typ.List[PostHandler]]

    async def begin(self) -> None:
        return

    async def cleanup(self) -> None:
        return

    def post_req(self, req: Typ.Tuple[str, Task]) -> None:
        if self._reqs.full():
            raise POSTPROC_NO_MORE_SPACE()

        self._reqs.put_nowait(req)

    async def run(self) -> None:
        while True:
            await self.PostProcWork_Step()

    async def PostProcWork_Step(self) -> None:
        key, task = await self._reqs.get()

        # To check that is this request able to
        # process.
        if key not in self._handlers:
            return

        # Process task
        handlers = self._handlers[key]
        for h in handlers:
            await h(task)

        await self.notify(
            self.NOTIFY_TASK_DONE, task.taskId)

    def addProc(self, key: str, handler: PostHandler):

        if key not in self._handlers:
            self._handlers[key] = []

        self._handlers[key].append(handler)

    def getHandlers(self, key: str) -> Typ.List[PostHandler]:
        if key not in self._handlers:
            raise POSTPROC_NO_HANDLERS_MATCH_WITH_THE_KEY(key)
        return self._handlers[key]
