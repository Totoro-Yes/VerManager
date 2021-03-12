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

# mmanager.py

import unittest
import asyncio
import threading
import abc

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from .util import partition
from .type import State, Ok, Error


class DaemonBase(ABC):

    @abc.abstractmethod
    def is_alive(self) -> bool:
        """ Is daemon still in running """

    @abc.abstractmethod
    def start(self) -> None:
        """ Start daemon """

    @abc.abstractmethod
    def stop(self) -> None:
        """  Stop daemon """


class Daemon(DaemonBase):

    def __init__(self) -> None:
        self.daemon = True
        self.alive = False
        self._t = None  # type: Optional[asyncio.Task]

    def is_alive(self) -> bool:
        return self.alive

    def stop(self) -> None:
        if self._t is not None:
            self._t.cancel()
            self._t = None

    @abstractmethod
    async def run(self) -> None:
        """ An asyncio method that do jobs """

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._t = loop.create_task(self.run())


class TDaemon(DaemonBase, threading.Thread):

    def __init__(self) -> None:
        threading.Thread.__init__(self)


class Module(ABC):

    def __init__(self, mName: str) -> None:
        self._mName = mName

    def getName(self) -> str:
        return self._mName

    def setName(self, name: str) -> None:
        self._mName = name

    @abstractmethod
    async def begin(self) -> None:
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        pass


class ModuleTDaemon(Module, TDaemon):

    def __init__(self, mName: str) -> None:
        Module.__init__(self, mName)
        TDaemon.__init__(self)


class ModuleDaemon(Module, Daemon):

    def __init__(self, mName: str) -> None:
        Module.__init__(self, mName)
        Daemon.__init__(self)


ModuleName = str


class MManager:

    def __init__(self):
        self._modules = {}  # type: Dict[ModuleName, Module]
        self._num = 0

    def isModuleExists(self, mName: ModuleName) -> bool:
        return mName in self._modules

    def numOfModules(self):
        return self._num

    def getModule(self, mName: ModuleName) -> Optional[Module]:
        if self.isModuleExists(mName):
            return self._modules[mName]

        return None

    def getAllModules(self) -> List[Module]:
        return list(self._modules.values())

    def getAlives(self) -> List[Module]:
        (alives, dies) = partition(list(self._modules.values()),
                                   lambda m: m.is_alive())
        return alives

    def getDies(self) -> List[Module]:
        (alives, dies) = partition(list(self._modules.values()),
                                   lambda m: m.is_alive())
        return dies

    def addModule(self, m: Module) -> State:
        mName = m.getName()

        if self.isModuleExists(mName):
            return Error

        self._modules[mName] = m
        self._num += 1

        return Ok

    async def removeModule(self, mName: ModuleName) -> Optional[Module]:
        if self.isModuleExists(mName):
            m = self._modules[mName]

            await m.cleanup()

            if isinstance(m, ModuleDaemon):
                m.stop()

            del self._modules[mName]
            self._num -= 1

            return m

        return None

    async def start(self, mName) -> None:
        if self.isModuleExists(mName):
            m = self._modules[mName]

            if isinstance(m, Module):
                await m.begin()
            if isinstance(m, DaemonBase):
                m.start()

    async def start_all(self) -> None:
        for m in self._modules.values():
            if isinstance(m, Module):
                await m.begin()
            if isinstance(m, DaemonBase):
                m.start()

    async def stop(self, mName) -> None:
        if self.isModuleExists(mName):
            m = self._modules[mName]
            await m.cleanup()
            if isinstance(m, DaemonBase):
                m.stop()

    def allDaemons(self) -> List:
        all = []
        for m in self.getAllModules():
            if isinstance(m, ModuleDaemon):
                all.append(m)
        return all

    async def stopAll(self) -> None:
        allMods = self.getAllModules()

        for mod in allMods:
            await mod.cleanup()
            if isinstance(mod, ModuleDaemon):
                mod.stop()

    async def join(self) -> None:
        while True:
            await asyncio.sleep(3600)


# TestCases
class ModuleExample(Module):

    def __init__(self, name: str) -> None:
        Module.__init__(self, name)

        self.running = False

    async def begin(self):
        self.running = True

    async def cleanup(self):
        self.running = False


class DaemonExample(ModuleDaemon):

    def __init__(self, name: str) -> None:
        ModuleDaemon.__init__(self, name)

        self.running = False
        self.done = False
        self.stoped = False

    async def begin(self) -> None:
        self.running = True

    async def cleanup(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.stoped = True

    def needStop(self) -> bool:
        return True

    async def run(self) -> None:
        self.done = True


class MManagerTestCases(unittest.TestCase):

    def setUp(self) -> None:
        self.manager = MManager()

        self.modules = modules = [ModuleExample("M1"), ModuleExample("M2")]
        self.daemons = daemons = [DaemonExample("D1"), DaemonExample("D2")]

        for m in modules:
            self.manager.addModule(m)

        for d in daemons:
            self.manager.addModule(d)

    def test_MManager_DaemonRuns(self):
        # Exercise
        runAwaits = (d.run() for d in self.manager.allDaemons())

        async def doTest() -> None:
            await asyncio.gather(*runAwaits)
        asyncio.run(doTest())

        # Verify
        for d in self.daemons:
            self.assertTrue(d.done)
