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
## \package tools nexdatas.configserver
## \file ndtscfg.py
# Command-line tool for ascess to configuration server
#


import sys
import os
import time

from optparse import OptionParser
from xml.dom.minidom import parse, parseString
import PyTango


## provides xml content of the node
# \param node DOM node
# \returns xml content string
def getText(node):
    if not node:
        return 
    xml = node.toxml() 
    start = xml.find('>')
    end = xml.rfind('<')
    if start == -1 or end < start:
        return ""
    return xml[start + 1:end].replace("&lt;","<").replace("&gt;","<").replace("&amp;","&")


## configuration server adapter
class ConfigServer(object):
    ## constructor
    # \param device device name of configuration server
    # \param nonewline no newline flag
    def __init__(self, device, nonewline=False):
        found = False
        cnt = 0
        ## spliting character
        self.__char = " " if nonewline else "\n"
        
        try:
            ## configuration server proxy
            self.cnfServer = PyTango.DeviceProxy(device)
        except Exception, e:
#            sys.stderr.write(str(e))
            found = True
            
        if found:
            sys.stderr.write("Error: Cannot connect into configuration server: %s\n"% device)
            sys.stderr.flush()
            sys.exit(0)

        while not found and cnt < 1000:
            if cnt > 1:
                time.sleep(0.01)
            try:
                if self.cnfServer.state() != PyTango.DevState.RUNNING:
                    found = True
            except Exception,e:
#                sys.stderr.write(str(e))
                time.sleep(0.01)
                found = False
            cnt +=1

        if not found:
            sys.stderr.write("Error: Setting up %s takes to long\n"% device)
            sys.stderr.flush()
            sys.exit(0)

            
#        if self.cnfServer.state() != PyTango.DevState.OPEN:
#            self.cnfServer.Init()
        self.cnfServer.Open()


    ## lists the DB item names
    # \param ds flag set True for datasources
    # \param mandatory flag set True for mandatory components        
    # \returns list op item names        
    def listCmd(self, ds, mandatory=False):
        if ds:
            if not mandatory:
                return self.cnfServer.AvailableDataSources()
        else:
            if mandatory:
                return self.cnfServer.MandatoryComponents()
            else:
                return self.cnfServer.AvailableComponents()
        return []    


    ## lists datasources of the component
    # \param component given component
    # \returns list of datasource names        
    def sourcesCmd(self, component):
        cmps = self.cnfServer.AvailableComponents()
        if component not in cmps:
            sys.stderr.write("Error: Component %s not stored in configuration server\n"% component)
            sys.stderr.flush()
            return []
        return self.cnfServer.ComponentDataSources(component)


    ## fetches record name or query from datasource node
    # \param node datasource node
    # \returns record name or query
    def getRecord(self, node):
        withRec = ["CLIENT", "TANGO"] 
        withQuery = ["DB"] 
        if node.nodeName == 'datasource':
            dsource = node
        else:
            dsource= node.getElementsByTagName("datasource")[0] \
                if len(node.getElementsByTagName("datasource")) else None 
        dstype = dsource.attributes["type"] if dsource and dsource.hasAttribute("type") else None
        if dstype.value in withRec:
            rec = dsource.getElementsByTagName("record")[0] \
                if dsource and len(dsource.getElementsByTagName("record")) else None
            rc = rec.attributes["name"] if rec.hasAttribute("name") else  None
            if rc:
                return rc.value
        elif dstype.value in withQuery:    
            query = getText(dsource.getElementsByTagName("query")[0]) \
                if len(dsource.getElementsByTagName("query")) else None
            if query and query.strip():
                return query.strip()
    
    ## lists datasources of the component
    # \param ds flag set True for datasources
    # \param name given component or datasource
    # \returns list of datasource names        
    def recordCmd(self, ds, name):
        records = []
        names = []
        interNames = []
        if not ds:
            cmps = self.cnfServer.AvailableComponents()
            if name not in cmps:
                sys.stderr.write("Error: Component %s not stored in configuration server\n"% name)
                sys.stderr.flush()
                return []
            xmlcp = self.cnfServer.Components([name])
            for xmlc in xmlcp:
                indom = parseString(xmlc)
                dsources = indom.getElementsByTagName("datasource")
                for dsrc in dsources:
                    dsname = dsrc.attributes["name"] if dsrc and dsrc.hasAttribute("name") else None
                    if dsname and dsname.value:
                        interNames.append(dsname.value)
                        rec = self.getRecord(dsrc)
                        if rec:
                            records.append(rec)
                    
                allNames = self.cnfServer.ComponentDataSources(name)
                for nm in allNames:
                    if nm not in interNames:
                        names.append(nm)
#            print "ALL", allNames
#            print "IN", interNames
#            print "N", names
        else:
            names.append(name)    

        dsrcs = self.cnfServer.AvailableDataSources()
        for nm in names:
            if nm not in dsrcs:
                sys.stderr.write("Error: Datasource %s not stored in configuration server\n"% nm)
                sys.stderr.flush()
                return []

        xmls = self.cnfServer.DataSources(names)
#        print xmls
        for xml in xmls:
            if xml:
                try:
                    indom = parseString(xml)
                    rec = self.getRecord(indom)
                    if rec:
                        records.append(rec)
                    
                except Exception,e:
                    sys.stderr.write("Error: Datasource %s cannot be parsed\n"% nm)
                    sys.stderr.write(str(e)+ '\n')
                    sys.stderr.flush()
                    return []
                

        return records


    ## shows the DB items
    # \param ds flag set True for datasources
    # \param args list of item names
    # \param mandatory flag set True for mandatory components        
    # \returns list of XML items         
    def showCmd(self, ds, args, mandatory=False):
        if ds:
            dsrc = self.cnfServer.AvailableDataSources()
            for ar in args:
                if ar not in dsrc:
                    sys.stderr.write("Error: DataSource %s not stored in configuration server\n"% ar)
                    sys.stderr.flush()
                    return []
            return self.cnfServer.DataSources(args)
        else:
            cmps = self.cnfServer.AvailableComponents()
            for ar in args:
                if ar not in cmps:
                    sys.stderr.write("Error: Component %s not stored in configuration server\n"% ar)
                    sys.stderr.flush()
                    return []
            if mandatory:
                mand =  list(self.cnfServer.MandatoryComponents())
                mand.extend(args)    
                return self.cnfServer.Components(mand)
            else:
                return self.cnfServer.Components(args)
        return []    


    ## Provides final configuration
    # \param ds flag set True for datasources
    # \param args list of item names
    # \returns XML configuration string
    def getCmd(self, ds, args):
        if ds:
            return ""
        else:
            cmps = self.cnfServer.AvailableComponents()
            for ar in args:
                if ar not in cmps:
                    sys.stderr.write(
                        "Error: Component %s not stored in configuration server\n"% ar)
                    sys.stderr.flush()
                    return ""
            self.cnfServer.CreateConfiguration(args)
            return self.cnfServer.XMLString
        return ""    


    ## perform requested command
    # \param command called command
    # \param ds flag set True for datasources
    # \param args list of item names
    # \param mandatory flag set True for mandatory components        
    # \returns resulting string
    def performCommand(self, command, ds, args, mandatory=False):
        if command == 'list':
            return  self.__char.join(self.listCmd(ds, mandatory)) 
        if command == 'show':
            return  self.__char.join(self.showCmd(ds, args, mandatory)) 
        if command == 'get':
            return  self.getCmd(ds, args) 
        if command == 'sources':
            return  self.__char.join(self.sourcesCmd(args[0]))
        if command == 'record':
            return  self.__char.join(self.recordCmd(ds, args[0]))
           
## provides XMLConfigServer device names
# \returns list of the XMLConfigServer device names
def getServers():
    try:
        db=PyTango.Database()
    except:
        sys.stderr.write(
            "Error: Cannot connect into the tango database on host: \n    %s \n "% os.environ['TANGO_HOST'])
        sys.stderr.flush()
        return ""
        
    servers = db.get_device_exported_for_class("XMLConfigServer").value_string
    return servers

## provides XMLConfigServer device name if only one or error in the other case
# \returns XMLConfigServer device name or empty string if error appears
def checkServer():
    servers = getServers()
    if not servers:
        sys.stderr.write(
            "Error: No XMLConfigServer on current host running. \n\n"
            +"    Please specify the server from the other host. \n\n")
        sys.stderr.flush()
        return ""
    if len(servers) > 1:
        sys.stderr.write(
            "Error: More than on XMLConfigServer on current host running. \n\n"
            +"    Please specify the server:\n        %s\n\n"% "\n        ".join(servers))
        sys.stderr.flush()
        return ""
    return servers[0]

## the main function
def main():
    
    
    ## pipe arguments
    pipe = []
    if not sys.stdin.isatty():
        ## system pipe 
        pipe = sys.stdin.readlines()

    #    commands = ['list','show','get', 'sources', 'record']
    commands = {'list':0,'show':0,'get':0, 'sources':1, 'record':1}
    ## run options
    options = None
    ## usage example
    usage = "usage: ndtscfg <command> [-s <config_server>] "\
            +" [-d] [-m] [<name1>] [<name2>] [<name3>] ... \n"\
            +" e.g.: ndtscfg list -s p02/xmlconfigserver/exp.01 -d\n\n"\
            + "Commands: \n"\
            + "   list [-s <config_server>]   \n"\
            + "          list names of available components\n"\
            + "   list [-s <config_server>] -d  \n"\
            + "          list names of available datasources\n"\
            + "   show [-s <config_server>]  component_name1 component_name2 ...  \n"\
            + "          show components with given names \n"\
            + "   show [-s <config_server>] -d dsource_name1 dsource_name2 ...  \n"\
            + "          show datasources with given names \n"\
            + "   get [-s <config_server>]  component_name1 component_name2 ...  \n"\
            + "          get merged configuration of components \n"\
            + "   sources [-s <config_server>]  component_name1  \n"\
            + "          get a list of component datasources \n"\
            + "   record [-s <config_server>]  component_name1  \n"\
            + "          get a list of datasource record names from component  \n"\
            + "   record [-s <config_server>]  -d  datasource_name1  \n"\
            + "          get a list of datasource record names   \n"\
            + "   servers [-s <config_server/host>] \n"\
            + "          get lists of configuration servers from the current tango host\n"\
            + " "
# db=PyTango.Database()
# db.get_device_exported_for_class("XMLConfigServer").value_string

    ## option parser
    parser = OptionParser(usage=usage)
    parser.add_option("-s","--server", dest="server", 
                      help="configuration server device name")
    parser.add_option("-d","--datasources",  action="store_true",
                      default=False, dest="datasources", 
                      help="perform operation on datasources")
    parser.add_option("-m","--mandatory",  action="store_true",
                      default=False, dest="mandatory", 
                      help="make use mandatory components as well")
    parser.add_option("-n","--no-newlines",  action="store_true",
                      default=False, dest="nonewlines", 
                      help="split result with space characters")

    (options, args) = parser.parse_args()

    if args and args[0] == 'servers':
        server = None
        if options.server and options.server.strip():
            server  = options.server.split("/")[0]
        if server: 
            server = server.strip()
        if server:
            if not ":" in server:
                server = server +":10000"
            localtango = os.environ['TANGO_HOST']
            os.environ['TANGO_HOST'] = server
            
        print "\n".join(getServers())
        if server:
            os.environ['TANGO_HOST'] = localtango 
        return

    if not options.server:
        options.server = checkServer()

    if not args or args[0] not in commands or not options.server :
        parser.print_help()
        print ""
        sys.exit(0)

        
    ## command-line and pipe arguments
    parg = args[1:]
    if pipe:
        parg.extend([p.strip() for p in pipe])

    if len(parg) < commands[args[0]]:
        parser.print_help()
        return


    ## configuration server     
    cnfserver = ConfigServer(options.server, options.nonewlines)
    


    ## result to print
    result = cnfserver.performCommand(args[0], options.datasources, 
                                      parg, options.mandatory)
    if result.strip():
        print result



if __name__ == "__main__":
    main()