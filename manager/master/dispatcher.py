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

from functools import reduce
from typing import Any, List, Optional, Callable, \
    Dict, Tuple, cast, Type
from collections import namedtuple
from threading import Condition
from manager.basic.observer import Subject, Observer
from manager.basic.mmanager import ModuleDaemon
from manager.master.worker import Worker
from manager.basic.type import Error
from manager.master.task import Task, SingleTask, PostTask
from manager.master.taskTracker import TaskTracker
from manager.master.workerRoom import WorkerRoom
from manager.basic.endpoint import Endpoint


M_NAME = "Dispatcher"

WaitAreaSpec = namedtuple('WaitAreaSpec', ['task_type', 'pri', 'num'])


class WaitArea:

    class Area_unknown_task(Exception):
        pass

    class Area_Full(Exception):
        pass

    class Area_Empty(Exception):
        pass

    def __init__(self, ident: str, specifics:  List[WaitAreaSpec]) -> None:
        self.ident = ident

        self._space = [
            (t, asyncio.Queue(num), pri) for t, pri, num in specifics
        ]  # type: List[Tuple[str, asyncio.Queue, int]]

        # Sort Queues by priority
        self._space.sort(key=lambda t: t[2])

        # For task append puerpose only.
        self._space_map = {t: queue for t, queue, _ in self._space}

        self._num_of_tasks = 0
        self._cond = asyncio.Condition()
        self._cond_no_async = Condition()

    async def enqueue(self, t: Any, timeout=None) -> None:
        try:
            q = self._space_map[type(t).__name__]
            await asyncio.wait_for(q.put(t), timeout=timeout)

            self._num_of_tasks += 1

        except KeyError:
            raise WaitArea.Area_unknown_task
        except asyncio.exceptions.TimeoutError:
            raise WaitArea.Area_Full

    def enqueue_nowait(self, t: Any) -> None:
        try:
            q = self._space_map[type(t).__name__]
            q.put_nowait(t)
            self._num_of_tasks += 1

        except KeyError:
            raise WaitArea.Area_unknown_task
        except asyncio.QueueFull:
            raise WaitArea.Area_Full

    async def dequeue(self, timeout=None) -> Any:
        async with self._cond:
            cond = await asyncio.wait_for(
                self._cond.wait_for(lambda: self._num_of_tasks > 0),
                timeout=timeout
            )

            if cond is False:
                raise WaitArea.Area_Empty()

        return self._dequeue()

    def dequeue_nowait(self) -> Any:
        with self._cond_no_async:
            cond = self._cond_no_async.wait_for(
                lambda: self._num_of_tasks > 0,
                timeout=0
            )

            if cond is False:
                raise WaitArea.Area_Empty()

        return self._dequeue()

    def _dequeue(self) -> Any:
        for _, q, _ in self._space:

            try:
                task = q.get_nowait()
                self._num_of_tasks -= 1
                return task

            except asyncio.QueueEmpty:
                pass

    def peek(self) -> Any:
        if self._num_of_tasks == 0:
            return None

        for _, q, _ in self._space:
            if len(q._queue) > 0:  # type: ignore
                return q._queue[0]  # type: ignore
            else:
                continue

    def all(self) -> List[Any]:
        all_content = []

        for _, q, _ in self._space:
            all_content += list(q._queue)  # type: ignore

        return all_content


class Dispatcher(ModuleDaemon, Subject, Observer, Endpoint):

    NOTIFY_LOG = "log"

    ENDPOINT_DISPATCH = 0
    ENDPOINT_CANCEL = 1

    def __init__(self) -> None:
        global M_NAME

        Endpoint.__init__(self)

        ModuleDaemon.__init__(self, M_NAME)

        Subject.__init__(self, M_NAME)
        self.addType(self.NOTIFY_LOG)

        Observer.__init__(self)

        self._stop = False

        # A queue contain a collection of tasks
        self._waitArea = WaitArea("Area", [
            WaitAreaSpec("PostTask", 0, 128),
            WaitAreaSpec("SingleTask", 1, 128)
        ])

        # An Event to indicate that there is some task in taskWait queue
        self.taskEvent = asyncio.Event()
        self.dispatchLock = asyncio.Lock()
        self._taskTracker = None  # type: Optional[TaskTracker]
        self._workers = None  # type: Optional[WorkerRoom]
        self._loop = asyncio.get_running_loop()
        self._search_cond = {}  # type: Dict[str, Callable]

    async def begin(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    def setWorkerRoom(self, wr: WorkerRoom) -> None:
        self._workers = wr

    def setTaskTracker(self, tt: TaskTracker) -> None:
        self._taskTracker = tt

    async def _log(self, msg: str) -> None:
        await self.notify(Dispatcher.NOTIFY_LOG, ("dispatcher", msg))

    # Dispatch a task to a worker of
    # all by overhead of workers
    #
    # return True if task is assign successful otherwise return False
    async def _dispatch(self, task: Task) -> bool:
        return await self._do_dispatch(task)

    async def _do_dispatch(self, task: Task) -> bool:
        """
        First to find a acceptable worker
        if found then assign task to the worker
        and _tasks otherwise append to taskWait
        """
        worker = self._search_proc_worker(task)

        # No workers satisfiy the condition.
        if worker is None:
            await self._log("Task " + task.id() +
                            " dispatch failed: No available worker")
            return False

        try:
            await worker.do(task)
            cast(TaskTracker, self._taskTracker).onWorker(task.id(), worker)
            await self._log(
                "Task " + task.id() + " dispatch to Worker("
                + worker.ident + ")"
            )
        except Exception:
            await self._log(
                "Task " + task.id() + " dispatch failed: Worker is\
                unable to do the task.")
            return False

        return True

    def _search_proc_worker(self, task: Task) -> Optional[Worker]:
        idx = type(task).__name__
        if idx not in self._search_cond:
            return None

        cond = self._search_cond[idx]
        workers = cast(WorkerRoom, self._workers)\
            .getWorkerWithCond_nosync(cond)
        if workers == []:
            return None
        else:
            return workers[0]

    def add_worker_search_cond(self, task_type: Type[Task],
                               cond: Callable) -> None:
        """
        Add a filter function to filter out wokrer that is able to
        process a type of tasks.

        If add multiple cond to a task type then the cond last added is work
        another is not.
        """
        t_typeName = task_type.__name__
        self._search_cond[t_typeName] = cond

    async def _dispatch_async(self, task: Task) -> bool:
        """
        Dispatch a task to workers.
        """
        await self._log("Dispatch task " + task.id())

        async with self.dispatchLock:
            if await self._dispatch(task) is False:
                # fixme: Queue may full while inserting
                await self._waitArea.enqueue(task)
                self.taskEvent.set()

            return True

    def dispatch(self, task: Task) -> None:
        # Task is already in process increase task's refs.
        if cast(TaskTracker, self._taskTracker).isInTrack(task.id()):
            task_exists = cast(TaskTracker, self._taskTracker)\
                .getTask(task.id())
            assert(task_exists is not None)
            task_exists.refs += 1

            return None

        cast(TaskTracker, self._taskTracker).track(task)

        # Dispatch task to workers
        self._loop.create_task(self._dispatch_async(task))

    async def redispatch(self, task: Task) -> bool:
        taskId = task.id()

        await self._log("Redispatch task " + taskId)

        # Set task's state to prepare and remove worker
        # deal with it before from record.
        ret = task.stateChange(Task.STATE_PREPARE)
        cast(TaskTracker, self._taskTracker).onWorker(task.id(), None)

        if ret is Error:
            cast(TaskTracker, self._taskTracker).untrack(task.id())
            return False

        async with self.dispatchLock:
            success = await self._do_dispatch(task)
            if not success:
                await self._waitArea.enqueue(task)
                self.taskEvent.set()

        return True

    async def run(self) -> None:

        assert(self._workers is not None)
        assert(cast(TaskTracker, self._taskTracker) is not None)

        self._loop.create_task(self._dispatching())

    def _peek_trimUntrackTask(self, area: WaitArea) -> Any:
        while True:
            task_peek = area.peek()
            if task_peek is None:
                return None
            else:
                ident = task_peek.id()
                if not cast(TaskTracker, self._taskTracker).isInTrack(ident):
                    # Drop untracked task
                    area.dequeue_nowait()
                    continue
                else:
                    return task_peek

    # Dispatcher thread that is respond to assign task
    # in queue which name is taskWait
    async def _dispatching(self) -> None:

        while True:
            await asyncio.sleep(1)

            if self.taskEvent.is_set():
                task_peek = self._peek_trimUntrackTask(self._waitArea)
                if task_peek is None:
                    self.taskEvent.clear()
                    continue

                # To check that is a worker available.
                cond = condChooser[type(task_peek).__name__]
                if cast(WorkerRoom, self._workers).\
                   getWorkerWithCond(cond) == []:

                    continue

                # Dispatch task to worker
                async with self.dispatchLock:
                    current = self._waitArea.dequeue_nowait()
                    success = await self._dispatch(current)
                    if not success:
                        await self._waitArea.enqueue(current)
            else:
                continue

    async def cancel(self, taskId: str) -> None:
        """
        Cancel task
        """
        task = cast(TaskTracker, self._taskTracker).getTask(taskId)

        if task is None:
            return None

        theWorker = cast(TaskTracker, self._taskTracker)\
            .whichWorker(task.id())

        if theWorker is not None and theWorker.isOnline():
            await theWorker.cancel(task.id())
            await self._log("Cancel task " + task.id())

        task.stateChange(Task.STATE_FAILURE)
        cast(TaskTracker, self._taskTracker).untrack(task.id())
        await self._log("Cancel task " + task.id())

    # Cancel all tasks processing on a worker
    def cancelOnWorker(self, wId: str) -> None:
        pass

    def removeTask(self, taskId: str) -> None:
        cast(TaskTracker, self._taskTracker).untrack(taskId)

    def getTask(self, taskId: str) -> Optional[Task]:
        return cast(TaskTracker, self._taskTracker).getTask(taskId)

    def getTaskInWaits(self) -> List[Task]:
        return self._waitArea.all()

    # Use to get result of task
    # after the call of this method task will be
    # remove from _tasks
    def retrive(self, taskId: str) -> Optional[str]:
        if not cast(TaskTracker, self._taskTracker).isInTrack(taskId):
            return None

        task = cast(TaskTracker, self._taskTracker).getTask(taskId)
        if task is None:
            return None

        if not task.isFinished():
            return None

        if task.refs > 0:
            task.refs -= 1

        return task.data

    def taskState(self, taskId: str) -> int:
        if not cast(TaskTracker, self._taskTracker).isInTrack(taskId):
            return Error

        task = cast(TaskTracker, self._taskTracker).getTask(taskId)
        if task is None:
            return Error

        return task.taskState()

    def isTaskExists(self, taskId: str) -> bool:
        return cast(TaskTracker, self._taskTracker).isInTrack(taskId)

    def _isTask(self, taskId: str, state: Callable) -> bool:
        if not cast(TaskTracker, self._taskTracker).isInTrack(taskId):
            return False

        task = cast(TaskTracker, self._taskTracker).getTask(taskId)
        if task is None:
            return False

        return state(task)

    def isTaskPrepare(self, taskId: str) -> bool:
        return self._isTask(taskId, lambda t: t.taskState()
                            == Task.STATE_PREPARE)

    def isTaskInProc(self, taskId: str) -> bool:
        return self._isTask(taskId, lambda t: t.taskState()
                            == Task.STATE_IN_PROC)

    def isTaskFailure(self, taskId: str) -> bool:
        return self._isTask(taskId, lambda t: t.taskState()
                            == Task.STATE_FAILURE)

    def isTaskFinished(self, taskId: str) -> bool:
        return self._isTask(taskId, lambda t: t.taskState()
                            == Task.STATE_FINISHED)

    async def workerLost_redispatch(self, worker: Worker) -> None:
        # No workers to dispatch task just return
        # and tasks on this worker will be drop by aging.
        if cast(WorkerRoom, self._workers).getNumOfWorkers() == 0:
            return None

        tasks = worker.inProcTasks()

        for t in tasks:
            # Clean record in TaskTracker
            cast(TaskTracker, self._taskTracker).onWorker(t.id(), None)

        for t in tasks:

            if isinstance(t, SingleTask):
                # This task is not depend on another task
                # just redispatch this task again.
                await self.redispatch(t)
            elif isinstance(t, PostTask):
                # Cause there is only one Merger
                # if it is lost, PostTask will unable to
                # redispatch. Just notify to JobMaster,
                # then it will cancel all tasks of the corresponding
                # job.
                await self.peer_notify((
                    t.id(),
                    Task.STATE_STR_MAPPING[Task.STATE_FAILURE]
                ))

    async def job_notify_handle(self, data: Any) -> None:
        """
        An handler to notify task state to JobMaster while
        task state changed event is come from EventListener
        """

        assert(self._taskTracker is not None)

        taskid, state = data

        if state == Task.STATE_FINISHED or state == Task.STATE_FAILURE:
            worker = cast(TaskTracker, self._taskTracker).whichWorker(taskid)
            assert(worker is not None)
            worker.removeTask(taskid)

            # Untrack the task
            self._taskTracker.untrack(taskid)

        await self.peer_notify((taskid, Task.STATE_STR_MAPPING[state]))

    async def handle(self, data: Any) -> None:
        cmd, task = data

        if cmd == Dispatcher.ENDPOINT_DISPATCH:
            # data :: Tuple[str, Task]
            self.dispatch(task)
        elif cmd == Dispatcher.ENDPOINT_CANCEL:
            # data :: Tuple[str, str]
            await self.cancel(task)


# Misc
# Method to get an online worker which
# with lowest overhead of all online workerd
def viaOverhead(workers: List[Worker]) -> List[Worker]:
    # Filter out workers which is not in online status or not able to accept
    onlineWorkers = acceptableWorkers(workers)

    if onlineWorkers == []:
        return []

    # Find out the worker with lowest overhead on a
    # collection of online acceptable workers
    normal_workers = findNormalWorkers(onlineWorkers)
    if normal_workers == []:
        return []

    def f(acc, w):
        return acc if acc.numOfTaskProc() <= w.numOfTaskProc() else w
    theWorker = reduce(f, normal_workers)

    return [theWorker]


def findNormalWorkers(workers: List[Worker]) -> List[Worker]:
    return [w for w in workers if w._role == Worker.ROLE_NORMAL]


def acceptableWorkers(workers: List[Worker]) -> List[Worker]:
    def f_online_acceptable(w):
        return w.isOnline() and w.isAbleToAccept()
    return list(filter(lambda w: f_online_acceptable(w), workers))


def theListener(workers: List[Worker]) -> List[Worker]:
    return [
        w for w in workers
        if w.isOnline() and w._role == Worker.ROLE_MERGER
    ]


condChooser = {
    'SingleTask': viaOverhead,
    'PostTask': theListener
}
