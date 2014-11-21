#!/usr/bin/env python
#   This file is part of nexdatas - Tango Server for NeXus data writer
#
#    Copyright (C) 2012-2013 DESY, Jan Kotanski <jkotan@mail.desy.de>
#
#    nexdatas is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    nexdatas is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with nexdatas.  If not, see <http://www.gnu.org/licenses/>.
## \package nexdatas nexdatas.tools
## \file nxsdata.py
# Command-line tool to ascess to  Tango Data Server
#
""" Set Up NeXus Tango Servers"""

import socket
import PyTango
import os
import sys
import time


class SetUp(object):

    def __init__(self):
        try:
            self.db = PyTango.Database()
        except:
            print "Can't connect to tango database on", \
                os.getenv('TANGO_HOST')
            sys.exit(255)

        self.writer_name = None
        self.cserver_name = None
        self._psub = None

    def restartServer(self, name, host=None):
        if name:
            if not host:
                host = socket.gethostname()
            admin = self.db.get_device_exported(
                'tango/admin/' + host).value_string
            if admin:
                adminproxy = PyTango.DeviceProxy('tango/admin/' + host)
                adminproxy = PyTango.DeviceProxy(admin[0])
                servers = adminproxy.read_attribute('Servers')
                started = adminproxy.command_inout(
                    "DevGetRunningServers", True)
                for vl in servers.value:
                    svl = vl.split('\t')[0]
                    if svl in started:
                        cname = svl.split('/')[0]
                        if cname == name:
                            adminproxy.DevStop(svl)
                            problems = True
                            print "Restarting:", svl,
                            counter = 0
                            while problems and counter < 1000:
                                try:
                                    print '.',
                                    adminproxy.DevStart(svl)
                                    problems = False
                                except:
                                    counter += 1
                                    time.sleep(0.1)
                            print " "
                            if problems:
                                print svl, "was not restarted"

    def startupServer(self, new, level, host, ctrl, device):
        server = self.db.get_server_class_list(new)
        if len(server) == 0:
            sys.stderr.write('Server ' + new.split('/')[0]
                             + ' not defined in database\n')
            return False

        adminproxy = PyTango.DeviceProxy('tango/admin/' + host)
        sinfo = self.db.get_server_info(new)
        sinfo.name = new
        sinfo.host = host
        sinfo.mode = ctrl
        sinfo.level = level
        self.db.put_server_info(sinfo)
        running = adminproxy.DevGetRunningServers(True)
        if new not in running:
            adminproxy.DevStart(new)
        adminproxy.UpdateServersInfo()

        print "waiting for server",

        found = False
        cnt = 0
        while not found and cnt < 1000:
            try:
                print "\b.",
                dp = PyTango.DeviceProxy(device)
                time.sleep(0.01)
                dp.ping()
                found = True
                print device, "is working"
            except:
                found = False
            cnt += 1
        return found

    def createDataWriter(self, beamline, masterHost):
        """Create DataWriter """
        if not beamline:
            print "createDataWriter: no beamline given "
            return 0
        if not masterHost:
            print "createDataWriter: no masterHost given "
            return 0

        class_name = 'NXSDataWriter'
        server = class_name
        server_name = server + '/' + masterHost
        full_class_name = 'NXSDataWriter/' + masterHost
        self.writer_name = "%s/nxsdatawriter/%s" % (beamline, masterHost)
        if not server_name in self.db.get_server_list(server_name):
            print "createDataWriter: creating " + server_name

            if server_name in self.db.get_server_list(server_name):
                print "createDataWriter: DB contains already " + server_name
                return 0

            di = PyTango.DbDevInfo()
            di.name = self.writer_name
            di._class = class_name
            di.server = server_name

            self.db.add_device(di)
            self.db.put_device_property(self.writer_name,
                                        {'NumberOfThreads': 100})

        hostname = socket.gethostname()

        self.startupServer(full_class_name, 1, hostname, 1, self.writer_name)

        return 1

    def createConfigServer(self, beamline, masterHost, jsonsettings=None):
        """Create DataWriter """
        if not beamline:
            print "createConfigServer: no beamline given "
            return 0
        if not masterHost:
            print "createConfigServer: no masterHost given "
            return 0

        class_name = 'NXSConfigServer'
        server = class_name
        server_name = server + '/' + masterHost
        self.cserver_name = "%s/nxsconfigserver/%s" % (beamline, masterHost)
        if not server_name in self.db.get_server_list(server_name):
            print "createConfigServer: creating " + server_name

            if server_name in self.db.get_server_list(server_name):
                print "createConfigServer: DB contains already " + server_name
                return 0

            di = PyTango.DbDevInfo()
            di.name = self.cserver_name
            di._class = class_name
            di.server = server_name

            self.db.add_device(di)
            self.db.put_device_property(
                self.cserver_name, {'VersionLabel': '%s@%s' % (
                        beamline.upper(), masterHost.upper())})

        hostname = self.db.get_db_host().split(".")[0]

        self.startupServer(server_name, 1, hostname, 1, self.cserver_name)

        dp = PyTango.DeviceProxy(self.cserver_name)
        if dp.state() != PyTango.DevState.ON:
            dp.Close()
        if jsonsettings:
            dp = PyTango.DeviceProxy(self.cserver_name)
            dp.JSONSettings = jsonsettings
        dp.Open()

        return 1

    def createSelector(self, beamline, masterHost, writer=None, cserver=None):
        """Create Selector Server """
        if not beamline:
            print "createSelector: no beamline given "
            return 0
        if not masterHost:
            print "createSelector: no masterHost given "
            return 0
        if writer:
            self.writer_name = writer
        if cserver:
            self.cserver_name = cserver

        class_name = 'NXSRecSelector'
        server = class_name
        server_name = server + '/' + masterHost
        full_class_name = 'NXSRecSelector/' + masterHost
        device_name = "%s/nxsrecselector/%s" % (beamline, masterHost)
        if not server_name in self.db.get_server_list(server_name):
            print "createSelector: creating " + server_name

            if server_name in self.db.get_server_list(server_name):
                print "createSelector: DB contains already " + server_name
                return 0

            di = PyTango.DbDevInfo()
            di.name = device_name
            di._class = class_name
            di.server = server_name
            self.db.add_device(di)

        hostname = socket.gethostname()

        self.startupServer(full_class_name, 1, hostname, 1, device_name)

        if self.writer_name or self.cserver_name:
            dp = PyTango.DeviceProxy(device_name)
            if self.writer_name:
                dp.writerDevice = self.writer_name
            if self.writer_name:
                dp.configDevice = self.cserver_name

        return 1
