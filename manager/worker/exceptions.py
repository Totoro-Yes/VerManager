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
#                              Monitor Exceptions                             #
###############################################################################
class INVALID_MONITOR_STATE(Exception):

    def __init__(self, state: int) -> None:
        self.state = state

    def __str__(self) -> str:
        return "Monitor has no state " + str(self.state)


###############################################################################
#                              Linker Exceptions                              #
###############################################################################
class LINK_NOT_EXISTS(Exception):

    def __init__(self, linkid) -> None:
        self.linkid = linkid

    def __str__(self) -> str:
        return "Link " + str(self.linkid) + " is not exists"


###############################################################################
#                             ProcUnit Exceptions                             #
###############################################################################
class RESULT_FILE_NOT_FOUND(Exception):

    def __init__(self, path) -> None:
        self.path = path

    def __str__(self) -> str:
        return "Result file not found: " + self.path
