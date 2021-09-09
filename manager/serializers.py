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


from .models import Versions, Revisions, JobHistory
from rest_framework import serializers


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Versions
        fields = ['vsn', 'sn', 'dateTime']


class RevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revisions
        fields = ['sn', 'author', 'comment', 'dateTime']


class JobHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobHistory
        fields = ['unique_id', 'job', 'filePath', 'dateTime']


class VersionInfoSerializer(serializers.Serializer):
    vsn = serializers.CharField(max_length=512)
    sn = serializers.CharField(max_length=512)
    is_temp = serializers.CharField(max_length=10)


class BuildInfoSerializer(serializers.Serializer):
    extra = serializers.CharField(max_length=60)
