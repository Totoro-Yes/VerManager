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
import unittest
import os
import shutil

from manager.master.persistentDB import PersistentDB
from manager.models import PersistentDBMeta


async def WriteRepeatly(db: PersistentDB, key: str,
                        data: bytes, count: int) -> None:
    while count > 0:
        await db.write(key, data)
        count -= 1


class PersistentDBTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.sut = PersistentDB("./PersistentDB")

    async def asyncTearDown(self) -> None:
        shutil.rmtree("./PersistentDB")

    async def test_PDB_Create(self) -> None:
        """
        Create PersistentDB
        """
        filePath = "./PersistentDB/TEST"

        await self.sut.create("TEST")
        self.assertTrue(PersistentDBMeta(key="TEST"))
        self.assertTrue(os.path.exists(filePath))
        await self.sut.remove("TEST")

    async def test_PDB_Remove(self) -> None:
        filePath = "./PersistentDB/TEST"

        await self.sut.create("TEST")
        await self.sut.remove("TEST")

        self.assertFalse(os.path.exists(filePath))

    async def test_PDB_Write(self) -> None:
        await self.sut.create("TEST")
        await self.sut.write("TEST", b"0123456", 0)
        await self.sut.write("TEST", b"a", 3)

        with open("./PersistentDB/TEST", "rb") as fd:
            data = fd.read(8)

        self.assertEqual(b"012a456", data)
        await self.sut.remove("TEST")

    async def test_PDB_Read(self) -> None:
        await self.sut.create("TEST")

        with open("./PersistentDB/TEST", "wb") as fd:
            fd.write(b"0123456")

        data = await self.sut.read("TEST", 7, 0)
        dataPos_3 = await self.sut.read("TEST", 3, 4)

        self.assertEqual(data, b"0123456")
        self.assertEqual(dataPos_3, b"456")

        await self.sut.remove("TEST")

    async def test_PDB_AtomicalCheck(self) -> None:
        await self.sut.create("TEST")

        # Run two repeat write concurrently.
        await asyncio.gather(
            WriteRepeatly(self.sut, "TEST", b"123", 100),
            WriteRepeatly(self.sut, "TEST", b"abc", 100)
        )

        # Make sure no data is overwrite by another.
        with open("./PersistentDB/TEST", "r") as fd:
            data = fd.read(3)
            self.assertTrue(data == "123" or data == "abc")
