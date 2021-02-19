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


import unittest
import os

from manager.master.persistentDB import PersistentDB
from manager.models import PersistentDBMeta
from channels.db import database_sync_to_async


class PersistentDBTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = PersistentDB("./PersistentDB")

    async def test_PDB_Create(self) -> None:
        """
        Create PersistentDB
        """
        filePath = "./PersistentDB/TEST"

        await database_sync_to_async(self.sut.create)("TEST")
        self.assertTrue(PersistentDBMeta(key="TEST"))
        self.assertTrue(os.path.exists(filePath))
        self.sut.remove("TEST")

    async def test_PDB_Remove(self) -> None:
        filePath = "./PersistentDB/TEST"

        self.sut.create("TEST")
        self.sut.remove("TEST")

        self.assertNotTrue(os.path.exists(filePath))

    async def test_PDB_Write(self) -> None:
        self.sut.create("TEST")
        self.sut.write("TEST", b"0123456", 0)
        self.sut.write("TEST", b"a", 3)

        with open("./PersistentDB/TEST", "rb") as fd:
            data = fd.read(8)

        self.assertEqual(b"0123a456", data)
        self.sut.remove("TEST")

    async def test_PDB_Read(self) -> None:
        self.sut.create("TEST")

        with open("./PersistentDB/TEST", "wb") as fd:
            fd.write(b"0123456")

        data = self.sut.read("TEST", 7, 0)
        dataPos_3 = self.sut.read("TEST", 3, 4)

        self.assertEqual(data, b"0123456")
        self.assertEqual(dataPos_3, b"456")

        self.sut.remove("TEST")
