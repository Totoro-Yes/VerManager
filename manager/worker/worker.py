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
import socket
import manager.worker.configs as configs

from typing import Callable
from manager.basic.letter import Letter
from manager.basic.info import Info
from manager.worker.connector import Connector
from manager.worker.processor import Processor
from manager.worker.procUnit import JobProcUnit, PostProcUnit
from manager.basic.dataLink import DataLinker, DataLink
from manager.worker.datalink import binaryStore, binaryStoreNotify
from manager.worker.monitor import Monitor
from manager.basic.debuger import Debuger
from manager.basic.logger import Logger


class Worker:

    def __init__(self, cfg_path: str) -> None:
        self.cfg = configs.config = Info(cfg_path)

    def start(self) -> None:
        asyncio.run(self.run())

    def start_nowait(self) -> None:
        asyncio.get_running_loop().create_task(self.run())

    async def run(self) -> None:
        # Create Logger
        logger = Logger("./log")
        logger.start()
        logger.handler_install(Processor.NAME, logger.listenTo)

        configs.logger = logger

        # Create Connector and Create Link
        connector = Connector()
        configs.connector = connector

        # Create Monitor
        monitor = Monitor(self.cfg.getConfig('WORKER_NAME'))
        monitor.setupConnector(connector)
        monitor.start()

        # Create Processor
        processor = Processor()
        processor.subscribe(Processor.PROC_LOG, configs.logger)
        monitor.track(processor.getMaintainer())

        processor.setup_output(connector)
        connector.set_msg_callback(msg_callback_gen(processor.req))

        # Create Link to Master
        master_address = self.cfg.getConfig('MASTER_ADDRESS')
        await connector.open_connection('Master', master_address['host'],
                                        master_address['port'])

        # Merger Setup
        role = self.cfg.getConfig('ROLE')
        merger_address = self.cfg.getConfig('MERGER_ADDRESS')

        if role == 'MERGER':
            # Setup PostProcUnit
            postProcUnit = PostProcUnit("Poster")
            processor.install_unit(postProcUnit)

            processor.set_type_dispatch_to_unit(Letter.BinaryFile, "Poster")
            processor.set_type_dispatch_to_unit(Letter.Post, "Poster")

            # Listen to another workers
            await connector.listen("Poster", merger_address['host'],
                                   merger_address['port'])

            # Create DataLink
            dataLinker = DataLinker()

            dataLinker.addDataLink(
                merger_address['host'], merger_address['dataPort'],
                DataLink.TCP_DATALINK, binaryStore, "./Post")
            dataLinker.addNotify("BINARY", binaryStoreNotify, processor)
            dataLinker.start()
        else:
            # Create Link to Merger if exists.
            if merger_address != '':
                host_addr = merger_address['host']
                if host_addr == '0.0.0.0':
                    host_addr = socket.gethostbyname(socket.gethostname())
                    await connector.open_connection('Poster', host_addr,
                                                    merger_address['port'])

            # Create ProcUnits and
            # Install ProcUnits into Processor
            jobProcUnit = JobProcUnit("Job")
            processor.install_unit(jobProcUnit)

            # Connector need info of JobProcUnit
            # so register an channel between them
            processor.register("Job", connector)

            # Setup dispatch
            processor.set_type_dispatch_to_unit(Letter.NewTask, "Job")

        # Start Processor
        processor.start()

        # Debug
        if configs.debug:
            debuger = Debuger(configs.debugRoutine)
            debuger.start()

        # Block Forever
        while True:
            await asyncio.sleep(3600)


def msg_callback_gen(f: Callable) -> Callable:
    async def cb(letter: Letter):
        f(letter)
    return cb
