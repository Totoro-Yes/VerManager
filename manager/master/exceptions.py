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


###############################################################################
#                                     Misc                                    #
###############################################################################
class COMPONENTS_LOG_NOT_INIT(Exception):
    pass


class INVALID_FORMAT_LETTER(Exception):
    pass


class INVALID_CONFIGURATIONS(Exception):
    pass


class Job_Command_Not_Found(Exception):

    def __init__(self, job_cmd_id: str) -> None:
        self._id = job_cmd_id

    def __str__(self) -> str:
        return "Job Command " + self._id + " not found."


class Job_Bind_Failed(Exception):
    pass


###############################################################################
#                            Proxy and MessageUnit                            #
###############################################################################
class UNABLE_SEND_MSG_TO_PROXY(Exception):

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def __str__(self) -> str:
        return "Unable to send message to Proxy cause: " \
        + self._reason


class MSG_WRAPPER_CFG_NOT_EXISTS(Exception):

    def __init__(self, cfg_key: str) -> None:
        self.cfg_key = cfg_key

    def __str__(self) -> str:
        return "MsgWrapper has no config \"" + self.cfg_key


class BASIC_CONFIG_IS_COVERED(Exception):

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return "Basic config \"" + self.name + "\" is covered."


###############################################################################
#                                    DocGen                                   #
###############################################################################
class DOC_GEN_FAILED_TO_GENERATE(Exception):

    def __str(self) -> str:
        return "Failed to generate log file."


class CUSTOM_FILE_NOT_FOUND(Exception):

    def __init__(self, path: str):
        self.path = path

    def __str__(self) -> str:
        return "custom.py is not found on path: " + self.path


class CUSTOM_FUNC_DOC_GEN_FAIL(Exception):

    def __init__(self, excep: Exception) -> None:
        self.excep = excep

    def __str__(self) -> str:
        return "doc_gen raise an exception: " + str(self.excep)


###############################################################################
#                                  JobMaster                                  #
###############################################################################
class UNABLE_TO_CREATE_META_FILE(Exception):

    def __init__(self, jobid: str, taskid: str) -> None:
        self.jobid = jobid
        self.taskid = taskid

    def __str__(self) -> str:
        return "Unable to create meta file for (" \
            + self.jobid + "," + self.taskid + ")"
