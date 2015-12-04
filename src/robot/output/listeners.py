#  Copyright 2008-2015 Nokia Solutions and Networks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import os.path

from robot.errors import DataError
from robot.utils import (Importer, is_string, py2to3,
                         split_args_from_name_or_path, type_name)

from .listenermethods import ListenerMethod, LibraryListenerMethod
from .loggerhelper import AbstractLoggerProxy
from .logger import LOGGER


@py2to3
class Listeners(object):
    _method_names = ('start_suite', 'end_suite', 'start_test', 'end_test',
                     'start_keyword', 'end_keyword', 'log_message', 'message',
                     'output_file', 'report_file', 'log_file', 'debug_file',
                     'xunit_file', 'library_import', 'resource_import',
                     'variables_import', 'close')

    def __init__(self, listeners):
        listeners = ListenerProxy.import_listeners(listeners,
                                                   self._method_names)
        for name in self._method_names:
            method = ListenerMethod(name, listeners)
            if name.endswith(('_file', '_import')):
                name = '_' + name
            self.__dict__[name] = method

    def imported(self, import_type, name, attrs):
        method = getattr(self, '_%s_import' % import_type.lower())
        method(name, attrs)

    def output_file(self, file_type, path):
        method = getattr(self, '_%s_file' % file_type.lower())
        method(path)

    def __nonzero__(self):
        return any(isinstance(method, ListenerMethod) and method
                   for method in self.__dict__.values())


class LibraryListeners(object):
    _method_names = ('start_suite', 'end_suite', 'start_test', 'end_test',
                     'start_keyword', 'end_keyword', 'log_message', 'message',
                     'close')

    def __init__(self):
        for name in self._method_names:
            self.__dict__[name] = LibraryListenerMethod(name)

    def _listener_methods(self):
        return [method for method in self.__dict__.values()
                if isinstance(method, LibraryListenerMethod)]

    def register(self, listeners, library):
        listeners = ListenerProxy.import_listeners(listeners,
                                                   self._method_names,
                                                   prefix='_',
                                                   raise_on_error=True)
        for method in self._listener_methods():
            method.register(listeners, library)

    def unregister(self, library, close=False):
        if close:
            self.close(library=library)
        for method in self._listener_methods():
            method.unregister(library)

    # FIXME: Better names needed....

    def xxx_suite(self):
        for method in self._listener_methods():
            method.start_suite()

    def yyy_suite(self):
        for method in self._listener_methods():
            method.end_suite()

    def imported(self, import_type, name, attrs):
        pass

    def output_file(self, file_type, path):
        pass


class ListenerProxy(AbstractLoggerProxy):
    _no_method = None

    def __init__(self, listener, method_names, prefix=None):
        listener, name = self._import_listener(listener)
        AbstractLoggerProxy.__init__(self, listener, method_names, prefix)
        self.name = name
        self.version = self._get_version(listener)

    def _import_listener(self, listener):
        if not is_string(listener):
            return listener, type_name(listener)
        name, args = split_args_from_name_or_path(listener)
        importer = Importer('listener')
        listener = importer.import_class_or_module(os.path.normpath(name),
                                                   instantiate_with_args=args)
        return listener, name

    def _get_version(self, listener):
        try:
            version = int(listener.ROBOT_LISTENER_API_VERSION)
            if version != 2:
                raise ValueError
        except AttributeError:
            raise DataError("Listener '%s' does not have mandatory "
                            "'ROBOT_LISTENER_API_VERSION' attribute."
                            % self.name)
        except (ValueError, TypeError):
            raise DataError("Listener '%s' uses unsupported API version '%s'."
                            % (self.name, listener.ROBOT_LISTENER_API_VERSION))
        return version

    @classmethod
    def import_listeners(cls, listeners, method_names, prefix=None,
                         raise_on_error=False):
        imported = []
        for listener in listeners:
            try:
                imported.append(cls(listener, method_names, prefix))
            except DataError as err:
                name = listener if is_string(listener) else type_name(listener)
                msg = "Taking listener '%s' into use failed: %s" % (name, err)
                if raise_on_error:
                    raise DataError(msg)
                LOGGER.error(msg)
        return imported
