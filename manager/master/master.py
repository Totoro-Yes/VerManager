# MIT License
#
# Copyright (c) 2020 Gcom Gcom
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

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import asyncio
import manager.master.eventHandlers as EVENT_HANDLERS
import manager.master.configs as cfg

from typing import Optional, List
from threading import Thread

from manager.master.task import PostTask, SingleTask
from manager.basic.type import State, Error
from manager.basic.mmanager import MManager, Module
from manager.basic.info import Info
from manager.basic.letter import Letter
from manager.master.workerRoom import WorkerRoom, M_NAME as WR_M_NAME
from manager.master.dispatcher import Dispatcher, M_NAME as DISPATCHER_M_NAME, \
    viaOverhead, theListener
from manager.master.eventListener \
    import EventListener, M_NAME as EVENT_M_NAME, Entry
from manager.master.eventHandlers import responseHandler, binaryHandler, \
    logHandler, logRegisterhandler, binaryNotify, NotifyHandle
from manager.master.logger import Logger
from manager.basic.storage import Storage
from manager.master.taskTracker import TaskTracker
from manager.master.verControl import RevSync
from manager.basic.dataLink import DataLinker, DataLink
from manager.master.jobMaster import JobMaster
from manager.master.proxy import Proxy
from manager.models import model_init


ServerInstance = None  # type:  Optional['ServerInst']


def get_module(mod_id: str) -> Optional[Module]:
    assert(ServerInstance is not None)
    return ServerInstance.getModule(mod_id)


predicates = [
    lambda cfgs:  "Address" in cfgs,
    lambda cfgs:  "Port" in cfgs,
    lambda cfgs:  "LogDir" in cfgs,
    lambda cfgs:  "ResultDir" in cfgs,
    lambda cfgs:  "GitlabUrl" in cfgs,
    lambda cfgs:  "PrivateToken" in cfgs,
    lambda cfgs:  "TimeZone" in cfgs
]


class ServerInst(Thread):

    def __init__(self, address: str, port: int, cfgPath: str) -> None:
        Thread.__init__(self)
        self._address = address
        self._port = port

        self._configPath = cfgPath

        self._mmanager = None  # type: Optional[MManager]

    def getModule(self, m: str) -> Optional[Module]:
        if self._mmanager is None:
            return None
        return self._mmanager.getModule(m)

    def addModule(self, mod: Module) -> State:
        if self._mmanager is None:
            return Error
        return self._mmanager.addModule(mod)

    def modules(self) -> List[Module]:
        if self._mmanager is None:
            return []
        return self._mmanager.getAllModules()

    async def _execute(self) -> None:
        global predicates

        # Initialize models
        await model_init()

        self._mmanager = MManager()
        cfg.mmanager = self._mmanager

        info = Info(self._configPath)

        # if not info.validityChecking(predicates):
        #    raise INVALID_CONFIGURATIONS

        self.addModule(info)

        workerRoom = WorkerRoom(self._address, self._port, self)
        self.addModule(workerRoom)

        tracker = TaskTracker()
        self.addModule(tracker)

        # JobMaster Init
        jobMaster = JobMaster()
        self.addModule(jobMaster)

        # Dispatcher Init
        dispatcher = Dispatcher()
        dispatcher.setWorkerRoom(workerRoom)
        dispatcher.setTaskTracker(tracker)
        # Setup task's worker search condition
        dispatcher.add_worker_search_cond(SingleTask, viaOverhead)
        dispatcher.add_worker_search_cond(PostTask, theListener)
        # Set as peer of JobMaster
        jobMaster.set_peer(dispatcher)

        self.addModule(dispatcher)

        # EventListener Init
        eventListener = EventListener()
        eventListener.registerEvent(Letter.Response, responseHandler)
        eventListener.registerEvent(Letter.LogRegister, logRegisterhandler)
        eventListener.registerEvent(Letter.Log, logHandler)
        eventListener.registerEvent(Letter.Notify, NotifyHandle.handle)
        self.addModule(eventListener)

        # EventHandler init
        env = Entry.EntryEnv(eventListener, eventListener.handlers,
                             self._mmanager)
        EVENT_HANDLERS.EVENT_HANDLER_TOOLS\
                      .action_init(env)

        logDir = info.getConfig('LogDir')
        logger = Logger(logDir)
        logger.log_register("misc")
        cfg.logger = logger
        self.addModule(logger)

        storage = Storage(info.getConfig('Storage'), self)
        self.addModule(storage)

        revSyncner = RevSync()
        self.addModule(revSyncner)

        # Subscribe to subjects
        eventListener.subscribe(EventListener.NOTIFY_LOST, workerRoom)
        workerRoom.subscribe(WorkerRoom.NOTIFY_CONN, eventListener)
        workerRoom.subscribe(WorkerRoom.NOTIFY_DISCONN, dispatcher)

        workerRoom.subscribe(WorkerRoom.NOTIFY_LOG, logger)
        eventListener.subscribe(EventListener.NOTIFY_LOG, logger)
        eventListener.subscribe(
            EventListener.NOTIFY_TASK_STATE_CHANGED, dispatcher)
        dispatcher.subscribe(Dispatcher.NOTIFY_LOG, logger)

        # Install observer handlers to EventListener
        async def new_worker_register(data):
            await eventListener.workerRegister(data)
        eventListener.handler_install(WR_M_NAME, new_worker_register)

        # Install observer handlers to WorkerRoom
        async def wr_handler_disconn(data):
            await workerRoom.notifyEvent(WorkerRoom.EVENT_DISCONNECTED, data)
        workerRoom.handler_install(EVENT_M_NAME, wr_handler_disconn)

        # Install observer handlers to Dispatcher
        async def handler_dispatcher(data):
            await dispatcher.workerLost_redispatch(data)
        dispatcher.handler_install(WR_M_NAME, handler_dispatcher)
        dispatcher.handler_install(EVENT_M_NAME, dispatcher.job_notify_handle)

        # Install log handler to logger
        for module in [EVENT_M_NAME, WR_M_NAME, DISPATCHER_M_NAME]:
            logger.handler_install(module, logger.listenTo)

        # DataLink Init
        dataPort = info.getConfig('dataPort')
        dataLinker = DataLinker()

        # Add a TCP DataLink used to transfer big binaryFile
        dataLinker.addDataLink(
            self._address, dataPort, DataLink.TCP_DATALINK,
            binaryHandler, env)
        dataLinker.addNotify("BINARY", binaryNotify, None)

        self._mmanager.addModule(dataLinker)

        # Add a UDP DataLink used to transfer Log of in doing jobs.
        # dataLinker.addDataLink(
        #    self._address, dataPort, DataLink.UDP_DATALINK,
        #    processor, args)

        # Proxy Init
        proxy = Proxy(1024)
        proxy.add_msg_source(jobMaster.M_NAME, jobMaster.source, {})
        self._mmanager.addModule(proxy)

        await self._mmanager.start_all()

        # Join to all modules
        await self._mmanager.join()

    def run(self) -> None:

        cfg.config = Info(self._configPath)

        # Start this server instance
        asyncio.run(self._execute())
