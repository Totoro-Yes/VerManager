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

# Create your tests here.

from manager.master.TestCases.eventListenerTestCases import \
    EntryTestCases, \
    EventListenerTestCases

from manager.master.TestCases.dispatcherTestCases import \
    WaitAreaTestCases, DispatcherUnitTest

from manager.master.task import \
    TaskTestCases

from manager.master.TestCases.workerRoomTestCases import \
    WorkerRoomTestCases

from manager.worker.TestCases.processorTestCases import \
    ProcessorTestCases

from manager.master.logger import \
    LoggerTestCases

# from manager.master.TestCases.verControlTestcases import VerControlTestCases

from manager.master.TestCases.taskTrackerTestCases import \
    TaskTrackerTestCases

from manager.master.TestCases.eventHandlerTestCases import EventHandlerTestCases

from manager.master.worker import \
    WorkerTestCases

from manager.basic.letter import \
    LetterTestCases

# from manager.basic.info import \
#     InfoTestCases

from manager.basic.storage import \
    StorageTestCases

from manager.master.build import \
    BuildTestCases

from manager.basic.observer import \
    ObTestCases

from manager.basic.mmanager import \
    MManagerTestCases

from manager.worker.TestCases.connectorTestCases import \
    LinkerTestCases

from manager.worker.TestCases.workerTestCases import \
    WorkerTestCases_

from manager.worker.TestCases.procUnitTestCases import \
    ProcUnitUnitTestCases, \
    JobProcUnitTestCases, \
    PostProcUnitTestCases

from manager.basic.TestCases.notifyTestCases import \
    NotifyTestCases

from manager.basic.TestCases.dataLinkTestCases import \
    DataLinkerTestCases

from manager.worker.TestCases.monitorTestCases import \
    MonitorTestCase

from manager.worker.TestCases.umaintainerTestCases import \
    UnitMaintainerTestCase

from manager.master.TestCases.jobTestCases import \
    JobTestCases

from manager.master.TestCases.proxyConfigsTestCases import \
    ProxyConfigsTestCases

from manager.master.TestCases.jobMasterTestCases import \
    JobMasterTestCases, JobMasterMiscTestCases

from manager.basic.TestCases.commandExecutorTestCases import \
    CommandExecutorTestCases

from manager.master.TestCases.proxyTestCases import \
    MsgWrapperTestCases, ProxyTestCases, MsgSourceTestCases


from manager.functionalTest import FunctionalTestCases


from manager.worker.TestCases.linkTestCases import \
    HBLinkTestCases

from manager.worker.TestCases.linkerTestCases import \
    LinkerTestCases

from manager.basic.TestCases.macroTestCases import MacroTestCases
