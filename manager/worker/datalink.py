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

import os
import traceback
from typing import Dict, BinaryIO, Optional, cast, Tuple
from manager.basic.letter import BinaryLetter
from manager.basic.dataLink import DataLink, DataLinkNotify
from manager.worker.processor import Processor


def post_file_create(post_dir: str, version: str, fileName: str) -> Optional[BinaryIO]:
    path = "/".join([post_dir, version])
    if not os.path.exists(path):
        os.makedirs(path)

    return open("/".join([path, fileName]), "wb")


class POST_BINARY_STORE_FAILED(Exception):
    pass


fds = {}  # type: Dict[str, BinaryIO]

async def binaryStore(dl: DataLink, bl: BinaryLetter,
                      post_dir: str) -> None:
    """
    Save binaryfile to to PostDir.
    """

    # Cause several file may transfer at the same time
    # so need a dict to keep track of all of in transfered file.
    global fds

    tid = bl.getTid()
    fileName = bl.getFileName()
    version = bl.getParent()
    menu = bl.getMenu()

    try:
        if tid not in fds:
            # A new transfer file.
            fd = post_file_create(post_dir, version, fileName)
            if fd is None:
                raise POST_BINARY_STORE_FAILED()
            else:
                fds[tid] = fd
        else:
            fd = fds[tid]

        bStr = bl.getBytes()
        if bStr == b"":
            # File transfer done
            fd.close()
            del fds[tid]

            # Notify to PostProcUnit that a file is transfer
            # finished.
            dl.notify(DataLinkNotify("BINARY", (version, tid, fileName, menu)))
        else:
            fd.write(bStr)
    except Exception:
        # Notify to PostProcUnit that a file is fail to
        # transfer
        dl.notify(DataLinkNotify("BINARY", (version, tid, "", "")))
        traceback.print_exc()


def binaryStoreNotify(msg: Tuple[str, str, str, str], proc: Processor) -> None:
    version, tid, fileName, menu= msg[0], msg[1], msg[2], msg[3]
    bl = BinaryLetter(tid, bStr=b"", fileName=fileName, menu=menu, parent=version)
    # Notify PostProcUnit via send letter to Processor.
    proc.req(bl)
