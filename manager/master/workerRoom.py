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

# connector.py
#
# Maintain connection with workers

import asyncio

from datetime import datetime
from manager.basic.observer import Subject, Observer
from manager.basic.type import State, Error, Ok
from manager.master.worker import Worker, WorkerInitFailed
from manager.basic.mmanager import ModuleDaemon
from manager.basic.commands import Command, LisAddrUpdateCmd
from manager.master.task import Task
from typing import Tuple, Callable, Any, List, Dict, Optional, cast
from manager.basic.info import M_NAME as INFO_M_NAME
from manager.basic.commands import AcceptCommand, AcceptRstCommand
from manager.basic.letter import receving, PropLetter

M_NAME = "WorkerRoom"

# Type alias
EVENT_TYPE = int
hookTuple = Tuple[Callable[[Worker, Any], None], Any]
filterFunc = Callable[[List[Worker]], List[Worker]]

# Constant
wrLog = "wrLog"


class WorkerRoom(ModuleDaemon, Subject, Observer):

    NOTIFY_LOG = "log"
    NOTIFY_CONN = "Conn"
    NOTIFY_IN_WAIT = "Wait"
    NOTIFY_DISCONN = "Disconn"

    WAITING_INTERVAL = 300

    EVENT_CONNECTED = 0
    EVENT_DISCONNECTED = 1
    EVENT_WAITING = 2

    def __init__(self, host: str, port: int, sInst: Any) -> None:
        global M_NAME

        # Module init
        ModuleDaemon.__init__(self, M_NAME)

        # Subject init
        Subject.__init__(self, M_NAME)
        self.addType(self.NOTIFY_CONN)
        self.addType(self.NOTIFY_IN_WAIT)
        self.addType(self.NOTIFY_DISCONN)
        self.addType(self.NOTIFY_LOG)

        # Observer init
        Observer.__init__(self)

        configs = sInst.getModule(INFO_M_NAME)

        # _workers is a collection of workers in online state
        self._workers = {}  # type: Dict[str, Worker]

        # Lock to protect _workers_waiting
        self._lock = asyncio.Lock()

        # _workers_waiting is a collection of workers in waiting state
        # if a worker which in this collection exceed WAIT limit it will
        # be removed
        self._workers_waiting = {}  # type: Dict[str, Worker]
        self.numOfWorkers = 0

        self._eventQueue = asyncio.Queue(256)  # type: asyncio.Queue

        self._lisAddr = ("", 0)

        self._host = host
        self._port = port

        self._WAITING_INTERVAL = configs.getConfig('WaitingInterval')
        if self._WAITING_INTERVAL == "":
            self._WAITING_INTERVAL = WorkerRoom.WAITING_INTERVAL

        self._stableThres = self._WAITING_INTERVAL + 1

        self._lastChangedPoint = datetime.utcnow()
        self._lastCandidates = []  # type: List[str]

        self._stop = False

    async def begin(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    def needStop(self) -> bool:
        return False

    async def _WR_LOG(self, msg: str) -> None:
        await self.notify(WorkerRoom.NOTIFY_LOG, (wrLog, msg))

    async def _accept_workers(self, r: asyncio.StreamReader,
                              w: asyncio.StreamWriter) -> None:

        # Init Worker
        try:
            propLetter = await receving(r, timeout=3)
            await self._WR_LOG("Worker Request arrived: " + str(propLetter))

            if propLetter is None:
                return

            w_ident = cast(PropLetter, propLetter).getIdent()
            role = cast(PropLetter, propLetter).getRole()
            max = int(cast(PropLetter, propLetter).getMax())

            if role == "MERGER":
                role_v = Worker.ROLE_MERGER
            else:
                role_v = Worker.ROLE_NORMAL

            arrived_worker = Worker(w_ident, r, w, role_v)
            arrived_worker.setState(Worker.STATE_ONLINE)
            arrived_worker.setMax(max)

            await self._WR_LOG("Worker " + w_ident + " is connected")

        except (ConnectionError, asyncio.exceptions.TimeoutError):
            w.close()
            return

        # Check that is a worker with same ident is already
        # in reside in WorkerRoom
        if self.isExists(w_ident):
            w.close()
            await self._WR_LOG("Worker " + w_ident + " is already exists")
            return

        await self._lock.acquire()

        if w_ident in self._workers_waiting:
            # fixme: socket of workerInWait is broken need to
            # change to acceptedWorker
            workerInWait = self._workers_waiting[w_ident]
            workerInWait.setStream(arrived_worker.getStream())

            # Note: Need to setup worker's status before listener
            #       address update otherwise
            #       listener itself will unable
            #       to know address changed.
            workerInWait.setState(Worker.STATE_ONLINE)

            self.addWorker(workerInWait)
            del self._workers_waiting[w_ident]

            await self.notify(WorkerRoom.NOTIFY_CONN, workerInWait)

            # Send an accept command to the worker
            # so it able to transfer message.
            await workerInWait.control(AcceptCommand())

            await self._WR_LOG("Worker " + w_ident + " is reconnect")

            self._lock.release()

            return None

        self._lock.release()

        # Need to reset the accepted worker
        # before it transfer any messages.
        await arrived_worker.control(AcceptRstCommand())

        self.addWorker(arrived_worker)
        await self.notify(WorkerRoom.NOTIFY_CONN, arrived_worker)

    async def run(self) -> None:
        server = await asyncio.start_server(
            self._accept_workers, self._host, self._port)
        await asyncio.gather(server.serve_forever(), self._maintain())

    def isStable(self) -> bool:
        diff = (datetime.utcnow() - self._lastChangedPoint).seconds
        return diff >= self._stableThres

    def setStableThres(self, thres: int) -> None:
        self._stableThres = thres

    def _changePoint(self) -> None:
        self._lastChangedPoint = datetime.utcnow()

    def getTaskOfWorker(self, wId: str, tid: str) -> Optional[Task]:
        worker = self.getWorker(wId)
        if worker is None:
            return None
        else:
            task = worker.searchTask(tid)

        return task

    def removeTaskFromWorker(self, wId: str, tid: str) -> None:
        worker = self.getWorker(wId)
        if worker is None:
            return None
        else:
            worker.removeTask(tid)

    # while eventlistener notify that a worker is disconnected
    # just change it's state into waiting. After <waiting_interval>
    # minutes if the workers is still disconnected then change
    # it's state into disconnected and wait several seconds
    # and remove from WorkerRoom
    #
    # Caution: Calling of hooks is necessary while a worker's state is changed
    async def _maintain(self) -> None:
        while True:
            await self._waiting_worker_update()
            await self._waiting_worker_processing(self._workers_waiting)
            await asyncio.sleep(1)

    async def _waiting_worker_update(self) -> None:
        try:
            (eventType, index) = self._eventQueue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        worker = self.getWorker(index)
        if worker is None:
            return None

        ident = worker.getIdent()

        if eventType == WorkerRoom.EVENT_DISCONNECTED:
            await self._WR_LOG(
                "Worker " + ident + " is in waiting state")

            # Update worker's counter
            worker.setState(Worker.STATE_WAITING)
            self.removeWorker(ident)
            self._workers_waiting[ident] = worker
            await self.notify(WorkerRoom.NOTIFY_IN_WAIT, worker)

    async def _waiting_worker_processing(
            self, workers: Dict[str, Worker]) -> None:

        workers_list = list(workers.values())

        if len(workers) == 0:
            return None

        outOfTime = [w for w in workers_list
                     if w.waitCounter() > self._WAITING_INTERVAL]

        await self._lock.acquire()

        for worker in outOfTime:
            ident = worker.getIdent()
            await self._WR_LOG("Worker " + ident +
                               " is disconnected")
            worker.setState(Worker.STATE_OFFLINE)

            await self.notify(WorkerRoom.NOTIFY_DISCONN, worker)
            del self._workers_waiting[ident]

        self._lock.release()

    async def notifyEvent(self, eventType: EVENT_TYPE, ident: str) -> None:
        await self._eventQueue.put((eventType, ident))

    def getWorker(self, ident: str) -> Optional[Worker]:
        if ident not in self._workers:
            return None
        return self._workers[ident]

    def getWorkerWithCond(self, condRtn: filterFunc) -> List[Worker]:
        workerList = list(self._workers.values())
        return condRtn(workerList)

    def getWorkerWithCond_nosync(self, condRtn: filterFunc) -> List[Worker]:
        workerList = list(self._workers.values())
        return condRtn(workerList)

    def getWorkers(self) -> List[Worker]:
        return list(self._workers.values())

    def addWorker(self, w: Worker) -> State:
        ident = w.getIdent()
        if ident in self._workers:
            return Error

        self._workers[ident] = w
        self.numOfWorkers += 1
        self._changePoint()

        return Ok

    def isExists(self, ident: str) -> bool:
        if ident in self._workers:
            return True
        else:
            return False

    def getNumOfWorkers(self) -> int:
        return self.numOfWorkers

    def getNumOfWorkersInWait(self) -> int:
        return len(self._workers_waiting)

    async def broadcast(self, command: Command) -> None:
        for w in self._workers.values():
            await w.control(command)

    async def control(self, ident: str, command: Command) -> State:
        try:
            await self._workers[ident].control(command)
        except KeyError:
            return Error
        except BrokenPipeError:
            return Error

        return Ok

    async def do(self, ident: str, t: Task) -> State:
        try:
            self._workers[ident].do(t)
        except KeyError:
            return Error
        except BrokenPipeError:
            return Error

        return Ok

    def removeWorker(self, ident: str) -> State:
        if ident not in self._workers:
            return Error

        del self._workers[ident]
        self.numOfWorkers -= 1
        self._changePoint()

        return Ok

    def tasks_clear(self) -> None:
        """ Remove all failure tasks from all workers """
        for w in self._workers.values():
            w.removeTaskWithCond(lambda t: t.isFailure())

    # Content of dictionary:
    # { PropertyName:PropertyValue }
    # e.g { "max":0, "sock":ref, "processing":0,
    #       "inProcTask":ref, "ident":name }
    def statusOfWorker(self, ident: str) -> Dict:
        worker = self.getWorker(ident)

        if worker is None:
            return {}

        return worker.status()

    def setState(self, ident: str, state: int) -> None:
        worker = self.getWorker(ident)

        if worker is None:
            return None

        worker.setState(state)
