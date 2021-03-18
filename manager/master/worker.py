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

# worker.py
#
# Maintain connection with workers and
# provide communication interface to another module

import traceback
import unittest
import asyncio

from manager.basic.commands import JobCancelCommand
from typing import Tuple, Optional, List, Dict, Callable
from .task import Task, TaskGroup
from datetime import datetime
from manager.basic.letter import Letter, receving as letter_receving, \
    sending as letter_sending
from manager.basic.commands import Command


WorkerState = int


class WorkerInitFailed(Exception):
    pass


class Worker:

    ROLE_MERGER = 0
    ROLE_NORMAL = 1

    STATE_ONLINE = 0
    STATE_WAITING = 1
    STATE_OFFLINE = 2
    STATE_PENDING = 3
    STATE_CLEAN = 4

    def __init__(self, ident: str,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 role: int) -> None:

        self._role = role

        self._reader = reader
        self._writer = writer
        self.address = "0.0.0.0"

        self.max = 0
        self.inProcTask = TaskGroup()
        self.menus = []  # type: List[Tuple[str, str]]
        self.ident = ident
        self.needUpdate = False

        # Before a PropertyNotify letter is report
        # from worker we see a worker as an offline
        # worker
        self.state = Worker.STATE_OFFLINE

        # Counters
        # 1.wait_counter: ther number of seconds
        #                 that a worker stay in STATE_WAITING
        # 2.offline_counter: the number of seconds that a worker
        #                    stay in STATE_OFFLINE
        # 3.online_counter: the number of seconds that a worker stay
        #                   in STATE_ONLINE
        # 4.clock: Record the time while state of Worker is changed
        #          and counter 1 to 3 is calculated via
        #          clock. Clock is not accessable by user directly.
        #
        # counters[STATE_ONLINE] : online_counter
        # counters[STATE_WAITING] : wait_counter
        # counters[STATE_OFFLINE] : offline_counter
        self.counters = [0, 0, 0, 0, 0]
        self._clock = datetime.now()

    def getStream(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return (self._reader, self._writer)

    def setStream(self, stream: Tuple[asyncio.StreamReader,
                                      asyncio.StreamWriter]) -> None:

        self._reader, self._writer = stream

    def waitCounter(self) -> int:
        self._counterSync()
        return self.counters[Worker.STATE_WAITING]

    def offlineCounter(self) -> int:
        self._counterSync()
        return self.counters[Worker.STATE_OFFLINE]

    def onlineCounter(self) -> int:
        self._counterSync()
        return self.counters[Worker.STATE_ONLINE]

    def _counterSync(self) -> None:
        delta = datetime.utcnow() - self._clock
        self.counters[self.state] = delta.seconds

    def setState(self, s: WorkerState) -> None:
        if self.state != s:
            self.counters[self.state] = 0

        self.state = s
        self._clock = datetime.utcnow()

    def getAddress(self) -> str:
        return self.address

    def setAddress(self, address: str) -> None:
        self.address = address

    def getIdent(self) -> str:
        return self.ident

    def isOnline(self) -> bool:
        return self.state == Worker.STATE_ONLINE

    def isWaiting(self) -> bool:
        return self.state == Worker.STATE_WAITING

    def isOffline(self) -> bool:
        return self.state == Worker.STATE_OFFLINE

    def isFree(self) -> bool:
        return self.inProcTask.numOfTasks() == 0

    def isAbleToAccept(self) -> bool:
        return self.inProcTask.numOfTasks() < self.max

    def searchTask(self, tid: str) -> Optional[Task]:
        return self.inProcTask.search(tid)

    def inProcTasks(self) -> List[Task]:
        return self.inProcTask.toList()

    def removeTask(self, tid: str) -> None:
        self.inProcTask.remove(tid)

    def removeTaskWithCond(self, predicate: Callable[[Task], bool]) -> None:
        return self.inProcTask.removeTasks(predicate)

    def setMax(self, max: int) -> None:
        self.max = max

    def maxNumOfTask(self) -> int:
        return self.max

    def numOfTaskProc(self) -> int:
        return self.inProcTask.numOfTasks()

    def isMerger(self) -> bool:
        return self._role == Worker.ROLE_MERGER

    async def control(self, cmd: Command) -> None:
        letter = cmd.toLetter()
        await self._send(letter)

    async def do(self, task: Task) -> None:
        letter = task.toLetter()

        if letter is None:
            raise Exception

        await self._send(letter)

        # Register task into task group
        task.toProcState()

        self.inProcTask.newTask(task)

    async def sendLetter(self, letter: Letter) -> None:
        await self._send(letter)

    async def waitLetter(self, timeout=None) -> Optional[Letter]:
        return await self.receving(self._reader, timeout=timeout)

    # Provide ability to cancel task in queue or
    # processed task
    # Note: sn here should be a verion sn
    async def cancel(self, id: str) -> None:

        task = self.inProcTask.search(id)

        # Task doesn not exist.
        if task is None:
            return None

        # Remove task from this worker
        self.inProcTask.remove(id)

        cmd = JobCancelCommand(id)
        await self.control(cmd)

    def status(self) -> Dict:
        status_dict = {
            "max": self.max,
            "processing": self.inProcTask.numOfTasks(),
            "inProcTask": self.inProcTask.toList_(),
            "ident": self.ident
        }
        return status_dict

    @staticmethod
    async def receving(reader: asyncio.StreamReader,
                       timeout=None) -> Optional[Letter]:
        return await letter_receving(reader, timeout=timeout)

    @staticmethod
    async def sending(writer: asyncio.StreamWriter, letter: Letter) -> None:
        return await letter_sending(writer, letter)

    async def _recv(self, timeout=None) -> Optional[Letter]:
        return await Worker.receving(self._reader, timeout=timeout)

    async def _send(self, letter: Letter) -> None:
        try:
            await Worker.sending(self._writer, letter)
        except Exception:
            traceback.print_exc()


# TestCases
class WorkerTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pass
