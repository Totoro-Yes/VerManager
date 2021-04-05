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

# EventListener

import traceback
import asyncio
import manager.master.configs as cfg

from django.utils import timezone

from collections import namedtuple
from typing import Callable, Any, Dict, List, Coroutine
from manager.basic.observer import Subject, Observer
from manager.basic.mmanager import ModuleDaemon
from manager.master.worker import Worker
from manager.basic.letter import Letter

# Test imports
from manager.basic.letter import HeartbeatLetter

M_NAME = "EventListener"

# Constant
letterLog = "letterLog"

Handler = Callable[['Entry.EntryEnv', Letter], Coroutine[Any, Any, None]]


class Entry:
    """
    An entry describe connection with a worker
    and logics that deal with event received
    from the worker.
    """
    EntryEnv = namedtuple('EntryEnv', 'eventListener handlers modules')

    def __init__(self, ident: str, worker, env: EntryEnv) -> None:
        self._ident = ident
        self._worker = worker
        self._env = env
        self._hbCount = 0
        self._hbTimer = timezone.now()
        self._hbTimerLimit = 10
        self._stop = False

    def getIdent(self) -> str:
        return self._ident

    def setHBTimeout(self, limit: int) -> None:
        self._hbTimerLimit = limit

    def setWorker(self, worker: Worker) -> None:
        self._worker = worker

    def getWorker(self) -> Worker:
        return self._worker

    def isEventExists(self, eventType: str) -> bool:
        return eventType in self._env.handlers

    async def stop(self) -> None:
        self._stop = True
        ident = self._worker.getIdent()
        eventL = self._env.eventListener

        await eventL.notify(eventL.NOTIFY_LOST, ident)
        eventL.remove(ident)
        eventL.removeEntry(ident)

    async def _heartbeatProc(self, hbEvent: HeartbeatLetter) -> None:
        seq = hbEvent.getSeq()
        if seq != self._hbCount:
            return None

        self._hbCount += 1
        self._hbTimer = timezone.now()

        hbEvent.setIdent("Master")
        await self._worker.sendLetter(hbEvent)

    def isHeartbeatTimeout(self, current) -> bool:
        interval = (current - self._hbTimer).seconds
        return interval >= self._hbTimerLimit

    async def _heartbeatMaintain(self) -> None:
        current = timezone.now()
        if self.isHeartbeatTimeout(current):
            await self.stop()

    async def eventProc(self) -> None:
        try:
            event = await self._worker.waitLetter(timeout=2)
        except asyncio.exceptions.TimeoutError:
            return

        if event is None:
            return None

        if isinstance(event, HeartbeatLetter):
            await self._heartbeatProc(event)
            return None

        type = event.typeOfLetter()

        try:
            # eventProc must not throw any of exceptions
            # if exceptions is catch from event handlers
            # need to log into logfile.
            for rtn in self._env.handlers[type]:
                await rtn(self._env, event)
        except Exception:
            traceback.print_exc()

    def start(self) -> None:
        asyncio.get_running_loop().\
            create_task(self.monitor())

    async def monitor(self) -> None:
        while True:
            if self._stop:
                return None

            try:
                await self.eventProc()
                await self._heartbeatMaintain()
            except Exception:
                # Print Exception
                traceback.print_exc()
                await self.stop()
                return


class EventListener(ModuleDaemon, Subject, Observer):

    NOTIFY_LOG = "log"
    NOTIFY_LOST = "lost"
    NOTIFY_TASK_STATE_CHANGED = "TSC"

    def __init__(self) -> None:
        global letterLog, M_NAME

        # Init as module
        ModuleDaemon.__init__(self, M_NAME)

        # Init as Subject
        Subject.__init__(self, M_NAME)
        self.addType(self.NOTIFY_LOG)
        self.addType(self.NOTIFY_LOST)
        self.addType(self.NOTIFY_TASK_STATE_CHANGED)

        # Init as Observer
        Observer.__init__(self)

        # Handler in handlers should be unique
        self.handlers = {}  # type: Dict[str, List[Handler]]

        # Registered Workers
        self.regWorkers = []  # type: List[Worker]

        self._regWorkerQ = asyncio.Queue(25)  # type: asyncio.Queue[Worker]

        # Entries
        self._entries = {}  # type: Dict[str, Entry]
        self._stop = False

        self._hbLimit = 5

    async def begin(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    def setHBTimeout(self, limit: int) -> None:
        self._hbLimit = limit

    async def _doStop(self) -> None:
        for ident in self._entries:
            self.stopEntry(ident)

    def needStop(self) -> bool:
        return self._stop

    def registerEvent(self, eventType: str, handler: Handler) -> None:
        if eventType in self.handlers:
            return None

        if eventType not in self.handlers:
            self.handlers[eventType] = []

        self.handlers[eventType].append(handler)

    def unregisterEvent(self, eventType: str) -> None:
        if eventType not in self.handlers:
            return None

        del self.handlers[eventType]

    def event_log(self, msg: str) -> None:
        self.notify(EventListener.NOTIFY_LOG, (letterLog, msg))

    def register(self, worker: Worker) -> None:
        if worker not in self.regWorkers:
            self.regWorkers.append(worker)

    def registered(self) -> List[Worker]:
        workerOfEntries = [e.getWorker() for e in self._entries.values()]
        return self.regWorkers + workerOfEntries

    def remove(self, ident: str) -> None:
        self.regWorkers = \
            [w for w in self.regWorkers if w.getIdent() != ident]

    def addEntry(self, entry: Entry) -> None:
        ident = entry.getIdent()

        if ident not in self._entries:
            self._entries[ident] = entry

    def removeEntry(self, ident: str) -> None:
        if ident in self._entries:
            del self._entries[ident]

    def stopEntry(self, ident: str) -> None:
        if ident in self._entries:
            self._entries[ident].stop()

    async def run(self) -> None:

        # Entry environment initialization
        entryEnv = Entry.EntryEnv(self, self.handlers, cfg.mmanager)

        while True:

            if self.needStop():
                await self._doStop()
                return None

            try:
                w = await asyncio.wait_for(
                    self._regWorkerQ.get(),
                    timeout=2
                )
            except asyncio.exceptions.TimeoutError:
                continue

            if w.getIdent() in self._entries:
                continue

            entry = Entry(w.getIdent(), w, entryEnv)
            entry.setHBTimeout(self._hbLimit)
            self.addEntry(entry)
            entry.start()

    async def workerRegister(self, worker: Worker) -> None:
        if worker in self.registered():
            return None

        self.register(worker)
        await self._regWorkerQ.put(worker)
