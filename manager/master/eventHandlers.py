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

# EventHandlers.py

import asyncio
import traceback
import concurrent.futures

import os
import zipfile
import shutil
import manager.master.configs as cfg
from VerManager.settings import DATA_URL
from manager.master.docGen import log_gen
from manager.master.exceptions import DOC_GEN_FAILED_TO_GENERATE

from typing import List, Dict, Optional, cast, Callable, Tuple, \
    Any
from collections import namedtuple

from manager.master.eventListener \
    import letterLog, Entry

from manager.basic.type import Error
from manager.basic.letter import Letter, \
    ResponseLetter, BinaryLetter, NotifyLetter

from manager.master.task import Task, SingleTask, PostTask
from manager.master.dispatcher import Dispatcher

from manager.basic.storage import StoChooser

from manager.master.dispatcher import M_NAME as DISPATCHER_M_NAME
from manager.master.logger import Logger, M_NAME as LOGGER_M_NAME

from manager.master.workerRoom import WorkerRoom, M_NAME as WR_M_NAME

from manager.basic.storage import M_NAME as STORAGE_M_NAME
from manager.basic.util import pathSeperator
from manager.basic.notify import Notify, WSCNotify
from manager.basic.dataLink import DataLink, DataLinkNotify

ActionInfo = namedtuple('ActionInfo', 'isMatch execute args')
path = str


class EVENT_HANDLER_TOOLS:

    ProcessPool = concurrent.futures.ProcessPoolExecutor()
    chooserSet = {}  # type: Dict[str, StoChooser]
    transfer_finished = {}  # type: Dict[str, path]

    PREPARE_ACTIONS = []  # type: List[ActionInfo]
    IN_PROC_ACTIONS = []  # type: List[ActionInfo]
    FIN_ACTIONS = []   # type: List[ActionInfo]
    FAIL_ACTIONS = []   # type: List[ActionInfo]

    ACTION_TBL = {
        Task.STATE_IN_PROC: IN_PROC_ACTIONS,
        Task.STATE_FINISHED: FIN_ACTIONS,
        Task.STATE_FAILURE: FAIL_ACTIONS
    }  # type: Dict[int, List[ActionInfo]]

    @classmethod
    def action_init(self, env: Entry.EntryEnv) -> None:
        # Fin action install
        singletask_fin_action_info = ActionInfo(
            isMatch=lambda t: isinstance(t, SingleTask),
            execute=self._singletask_fin_action,
            args=env
        )
        self.install_action(Task.STATE_FINISHED, singletask_fin_action_info)

        posttask_fin_action_info = ActionInfo(
            isMatch=lambda t: isinstance(t, PostTask),
            execute=self._posttask_fin_action,
            args=env
        )
        self.install_action(Task.STATE_FINISHED, posttask_fin_action_info)

        task_common_fin_action_info = ActionInfo(
            isMatch=lambda t: True,
            execute=self._tasks_fin_action,
            args=env
        )
        self.install_action(Task.STATE_FINISHED, task_common_fin_action_info)

        # Fail action install
        task_common_fail_action_info = ActionInfo(
            isMatch=lambda t: True,
            execute=self._tasks_fail_action,
            args=env
        )
        self.install_action(Task.STATE_FAILURE, task_common_fail_action_info)

    @classmethod
    async def do_action(self, t: Task, state: int) -> None:
        actions = self.ACTION_TBL[state]

        for action in actions:
            if action.isMatch(t):
                await action.execute(t, action.args)

    @classmethod
    def install_action(self, state: int, action: ActionInfo) -> None:
        self.ACTION_TBL[state].append(action)

    @classmethod
    async def packDataWithChangeLog(self, vsn: str, filePath: str, dest: str) -> str:
        pathSplit = filePath.split("/")
        pathSplit[-1] = pathSplit[-1] + ".log.rar"
        zipPath = "/".join(pathSplit)
        zipFileName = zipPath.split("/")[-1]

        try:
            await log_gen(vsn, "./log.txt")
        except DOC_GEN_FAILED_TO_GENERATE:
            # Fail to generate log file
            # log into log file.
            return filePath

        # Pack into a zipfile may take a while
        # do it in another process.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            EVENT_HANDLER_TOOLS.ProcessPool,
            self.zipPackHelper,
            ["./log.txt", filePath], zipPath
        )

        return zipFileName

    @staticmethod
    def changeLogGen(start_commit: str,
                     last_commit: str,
                     destPath: str) -> None:

        from manager.models import infoBetweenRev
        changeLog = infoBetweenRev(start_commit, last_commit)

        with open(destPath, "w") as logFile:
            for log in changeLog:
                logFile.write(log)

    @staticmethod
    def zipPackHelper(files: List[str], zipPath: str) -> None:
        zipFd = zipfile.ZipFile(zipPath, "w")
        for f in files:
            zipFd.write(f)
        zipFd.close()

    @staticmethod
    async def _singletask_fin_action(
            t: SingleTask, env: Entry.EntryEnv) -> None:

        if t.job.numOfTasks() == 1:
            await responseHandler_ResultStore(t, env)

    @staticmethod
    async def _posttask_fin_action(t: PostTask, env: Entry.EntryEnv) -> None:
        Temporary = t.job.get_info('Temporary')

        if Temporary is not None and Temporary == 'true':
            await temporaryBuild_handling(t, env)
        else:
            await responseHandler_ResultStore(t, env)

        t.toFinState()

    @staticmethod
    async def _tasks_fin_action(t: Task, env: Entry.EntryEnv) -> None:
        return None

    @staticmethod
    async def _tasks_fail_action(t: Task, env: Entry.EntryEnv) -> None:
        return None


async def responseHandler(
        env: Entry.EntryEnv, letter: Letter) -> None:

    if not isinstance(letter, ResponseLetter):
        return None

    ident = letter.getHeader('ident')
    taskId = letter.getHeader('tid')
    state = int(letter.getContent('state'))

    wr = env.modules.getModule('WorkerRoom')  # type: WorkerRoom
    task = wr.getTaskOfWorker(ident, taskId)

    if task is None or not Task.isValidState(state):
        return None

    if task.stateChange(state) is Error:
        return None

    await EVENT_HANDLER_TOOLS.do_action(task, state)

    # Notify to components that
    # task's state is changed.
    type = env.eventListener.NOTIFY_TASK_STATE_CHANGED
    await env.eventListener.notify(type, (taskId, state))


async def copyFileInExecutor(src: str, dest: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        EVENT_HANDLER_TOOLS.ProcessPool,
        shutil.copy,
        src, dest)


async def temporaryBuild_handling(
        task: Task, env: Entry.EntryEnv) -> None:

    logger = env.modules.getModule('Logger')

    chooserSet = EVENT_HANDLER_TOOLS.chooserSet
    seperator = pathSeperator()
    taskId = task.id()

    chooser = chooserSet[taskId]
    filePath = chooser.path()
    fileName = filePath.split(seperator)[-1]

    try:
        if not os.path.exists("private"):
            os.mkdir("private")

        # Copy may happen on NFS may take a long time to deal
        # just run in another process.
        await copyFileInExecutor(filePath, "private" + seperator + fileName)

    except FileNotFoundError as e:
        Logger.putLog(logger, letterLog, str(e))
    except PermissionError as e:
        Logger.putLog(logger, letterLog, str(e))


async def responseHandler_ResultStore(
        task: Task, env: Entry.EntryEnv) -> None:

    assert(cfg.config is not None)

    logger = env.modules.getModule('Logger')

    taskId = task.id()
    extra = task.getExtra()

    trans_fin = EVENT_HANDLER_TOOLS.transfer_finished
    path = trans_fin[taskId]

    seperator = pathSeperator()
    fileName = path.split(seperator)[-1]
    resultDir = cfg.config.getConfig("ResultDir")

    try:
        fileName = await EVENT_HANDLER_TOOLS.packDataWithChangeLog(
            task.getVSN(), path, resultDir)

    except FileNotFoundError as e:
        traceback.print_exc()
        await Logger.putLog(logger, letterLog, str(e))
    except PermissionError as e:
        traceback.print_exc()
        await Logger.putLog(logger, letterLog, str(e))
    except Exception:
        traceback.print_exc()

    task.job.job_result = job_result_url(taskId.split("_")[0], fileName)


def job_result_url(unique_id: str, fileName: str) -> str:
    may_slash = "" if DATA_URL[-1] == '/' else "/"
    return DATA_URL + may_slash + unique_id + "/" + fileName


def cmd_log_handler(dl: DataLink, letter: Letter, args: Any) -> None:
    print(letter)


async def binaryHandler(dl: DataLink, letter: BinaryLetter,
                        env: Entry.EntryEnv) -> None:
    chooserSet = EVENT_HANDLER_TOOLS.chooserSet

    if not isinstance(letter, BinaryLetter):
        return None

    tid = letter.getHeader('tid')
    unique_id = tid.split("_")[0]

    # A new file is transfered.
    if unique_id not in chooserSet:
        fileName = letter.getFileName()

        sto = env.modules.getModule(STORAGE_M_NAME)
        chooser = sto.create(unique_id, fileName)
        chooserSet[unique_id] = chooser

    chooser = chooserSet[unique_id]
    content = letter.getContent('bytes')

    if content == b"":
        # A file is transfer finished.
        chooser.close()
        del chooserSet[unique_id]

        # Notify To DataLinker a file is transfered finished.
        dl.notify(DataLinkNotify("BINARY", (tid, chooser.path())))
    else:
        chooser.store(content)


def binaryNotify(msg: Tuple[str, str], arg: Any) -> None:
    tid, path = msg[0], msg[1]
    transfered = EVENT_HANDLER_TOOLS.transfer_finished

    if tid in transfered:
        return None

    transfered[tid] = path


async def logHandler(env: Entry.EntryEnv, letter: Letter) -> None:
    logger = env.modules.getModule(LOGGER_M_NAME)

    logId = letter.getHeader('logId')
    logMsg = letter.getContent('logMsg')

    if isinstance(logMsg, str):
        await Logger.putLog(logger, logId, logMsg)


async def logRegisterhandler(env: Entry.EntryEnv, letter: Letter) -> None:
    logger = env.modules.getModule(LOGGER_M_NAME)
    logId = letter.getHeader('logId')
    logger.log_register(logId)




###############################################################################
#                               Notify Handlers                               #
###############################################################################
class NotifyHandle:

    @classmethod
    async def handle(self, env: Entry.EntryEnv, nl: Letter) -> None:

        if not isinstance(nl, NotifyLetter):
            return None

        handler = self._search_handler(nl)
        if handler is None:
            return None
        await handler(env, nl)

    @classmethod
    def _search_handler(self, nl: NotifyLetter) -> Optional[Callable]:
        type = nl.notifyType()
        try:
            return getattr(NotifyHandle, 'NOTIFY_H_'+type)
        except AttributeError:
            raise NOTIFY_NOT_MATCH_WITH_HANDLER(type)

    @classmethod
    async def NOTIFY_H_WSC(self, env: Entry.EntryEnv, nl: NotifyLetter) -> None:
        """
        Change state of correspond worker.
        """
        wsc_notify = cast(WSCNotify, Notify.transform(nl))
        who = wsc_notify.fromWho()
        state = wsc_notify.state()

        wr = env.modules.getModule(WR_M_NAME)  # type: WorkerRoom
        wr.setState(who, int(state))


class NOTIFY_NOT_MATCH_WITH_HANDLER(Exception):

    def __init__(self, type: str) -> None:
        self._type = type

    def __str__(self) -> str:
        return "Notify " + self._type + " not match with any handler"
