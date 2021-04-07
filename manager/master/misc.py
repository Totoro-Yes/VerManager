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
import typing as Typ
import zipfile
from functools import reduce
from manager.master.docGen import log_gen
from manager.master.task import Task
from manager.master.exceptions import DOC_GEN_FAILED_TO_GENERATE
from concurrent.futures import ProcessPoolExecutor
from VerManager.settings import DATA_URL


###############################################################################
#                                   PostProc                                  #
###############################################################################
General_PostProc = "General"


def zipPackHelper(files: Typ.List[str], zipPath: str) -> None:
    zipFd = zipfile.ZipFile(zipPath, "w")
    for f in files:
        zipFd.write(f)
    zipFd.close()


def job_result_url(unique_id: str, path: str) -> str:
    fileName = path.split("/")[-1]
    may_slash = "" if DATA_URL[-1] == '/' else "/"
    return DATA_URL + may_slash + unique_id + "/" + fileName


async def postProcAttachLog(task: Task, path: str) -> None:
    try:
        await postProcAttachLog_work(task, path)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise e

    import sys
    sys.stdout.flush()
    sys.stderr.flush()


async def postProcAttachLog_work(task: Task, path: str) -> None:
    job_uid = str(task.job.unique_id)

    zipPath = reduce(
        lambda arg, f: f(arg),
        [lambda p: p.split("/"),
         lambda pList: "/".join(pList[:-1]+[pList[-1] + ".log.rar"])],
        path
    )

    try:
        await log_gen(task.getVSN(), "./log.txt")
    except DOC_GEN_FAILED_TO_GENERATE:
        task.job.job_result = job_result_url(job_uid, path)

    with ProcessPoolExecutor() as e:
        await asyncio.get_running_loop()\
            .run_in_executor(
                e, zipPackHelper,
                ["./log.txt", path], zipPath)

    task.job.job_result = job_result_url(job_uid, zipPath)
