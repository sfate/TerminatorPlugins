'''
Created on May 6, 2012

@author: Daniel Marohn
'''

import gtk
import terminatorlib.plugin as plugin
from terminatorlib.util import dbg, err
from terminatorlib.translation import _
from terminatorlib.config import Config
import uuid
from os import path

EXPORTER_NAME="TerminalExporter"

SETTING_DIR = "directory"
SETTING_EXPORT_FILE = "exportNameToFile"
SETTING_EXPORT_ENV = "exportNameToEnv"
SETTING_MENU_MAIN = "mainMenuText"
SETTING_MENU_EXPORT = "exportMenuText"
SETTING_MENU_STOP_LOG = "stopLogMenuText"
SETTING_MENU_START_LOG = "logMenuText"
SETTING_MENU_EXPORT_LOG = "exportLogMenuText"
DEFAULT_SETTINGS = {SETTING_DIR            : "/tmp",
                    SETTING_EXPORT_FILE    : "/tmp/.terminatorExports",
                    SETTING_EXPORT_ENV     : "",
                    SETTING_MENU_MAIN      : EXPORTER_NAME,
                    SETTING_MENU_EXPORT    : "export terminal",
                    SETTING_MENU_STOP_LOG  : "stop log",
                    SETTING_MENU_START_LOG : "log terminal",
                    SETTING_MENU_EXPORT_LOG: "export and log terminal",
                    }


AVAILABLE = [EXPORTER_NAME,]
#older versions of terminator require available instead of AVAILABLE
available = AVAILABLE

def parsePluginConfig(config):
    '''merge the default settings with settings from terminator's config'''
    ret = DEFAULT_SETTINGS
    pluginConfig = config.plugin_get_config(EXPORTER_NAME)
    if pluginConfig:
        for currentKey in ret.keys():
            if currentKey in pluginConfig:
                ret[currentKey] = pluginConfig[currentKey]
        for currentKey in pluginConfig:
            if not currentKey in ret:
                err("invalid config parameter: %s" % currentKey)
    return ret

class LogParameter():
    '''Container class, holding information about a logged terminal'''
    def __init__(self, watcher, filename, lastLoggedLine = -1):
        '''
        @param watcher: the gtk object, returned by vte.connect
        @param filename: terminal output is logged into this file
        @param lastLoggedLine: number of last line number that was written to file
        '''
        self.watcher = watcher
        self.lastLoggedLine = lastLoggedLine
        self.filename = filename
 
class TerminalExporter(plugin.MenuItem):
    '''
    plugin that allows to export full terminal content into file,
    and provides a logging function for a terminal.
    '''
    
    capabilities = ['terminal_menu']
    
    def __init__(self):
        plugin.MenuItem.__init__(self)
        self.config = Config()
        self.pluginConfig = parsePluginConfig(self.config)
        self.loggingTerminals = {}
        self.scrollbackLines = self.config['scrollback_lines']
        dbg("using config: %s" % self.pluginConfig)
    
    def callback(self, menuitems, menu, terminal):
        '''called by terminator on context menu open'''
        item = gtk.MenuItem(_(self.pluginConfig[SETTING_MENU_MAIN]))
        submenu = gtk.Menu()
        exportItem = gtk.MenuItem(_(self.pluginConfig[SETTING_MENU_EXPORT]))
        exportItem.connect("activate", self.doExport, terminal)
        submenu.append(exportItem)
        if terminal in self.loggingTerminals:
            logItem = gtk.MenuItem(_(self.pluginConfig[SETTING_MENU_STOP_LOG]))
            logItem.connect("activate", self.doStopLog, terminal)
            submenu.append(logItem)
        else:
            logItem = gtk.MenuItem(_(self.pluginConfig[SETTING_MENU_START_LOG]))
            logItem.connect("activate", self.doLog, terminal)
            submenu.append(logItem)
            logItem = gtk.MenuItem(_(self.pluginConfig[SETTING_MENU_EXPORT_LOG]))
            logItem.connect("activate", self.doExportLog, terminal)
            submenu.append(logItem)
        item.set_submenu(submenu)
        menuitems.append(item)
    
    def doExportLog(self, widget, terminal):
        filename = self.doExport(widget, terminal)
        self.doLog(widget, terminal, filename)
    
    def doExport(self, widget, terminal):
        """
        Export complete terminal content into file.
        """
        vte = terminal.get_vte()
        (startRow, endRow, endColumn) = self.getVteBufferRange(vte)
        content = vte.get_text_range(startRow, 0, endRow, endColumn, 
                                    lambda widget, col, row, junk: True)
        filename = self.getFilename()
        with open(filename, "w") as outputFile: 
            outputFile.writelines(content)
            outputFile.close()
        dbg("terminal content written to [%s]" % filename)
        if self.pluginConfig[SETTING_EXPORT_ENV] != "":
            terminal.feed('%s="%s"\n' % (self.pluginConfig[SETTING_EXPORT_ENV] ,filename))
        return filename
                
    def doLog(self, widget, terminal, filename = None):
        if filename == None:
            filename = self.getFilename()
        vte = terminal.get_vte()
        (startrow, endrow, endColumn) = self.getVteBufferRange(vte)
        watcher = vte.connect('contents-changed',  self.logNotify, terminal)
        parameter = LogParameter(watcher, filename, endrow)
        self.loggingTerminals[terminal] = parameter

    def doStopLog(self, widget, terminal):
        vte = terminal.get_vte()
        vte.disconnect(self.loggingTerminals.pop(terminal).watcher)

    def logNotify(self, _vte, terminal):
        vte = terminal.get_vte()
        (startrow, endRow, endColumn) = self.getVteBufferRange(vte)
        parameter = self.loggingTerminals[terminal]
        if endRow > parameter.lastLoggedLine:
            content = vte.get_text_range(parameter.lastLoggedLine + 1, 0, endRow, endColumn, 
                                    lambda widget, col, row, junk: True)
            with open(parameter.filename, "a") as outputFile:
                outputFile.writelines(content)
                outputFile.close()
            parameter.lastLoggedLine = endRow

    def getVteBufferRange(self, vte):
        """
        Get the range of a vte widget.
        """
        endColumn, endrow = vte.get_cursor_position()
        if self.scrollbackLines < 0:
            startrow = 0
        else:
            startrow = max(0, endrow - self.scrollbackLines)
        return(startrow, endrow, endColumn)

    def getFilename(self):
        filename = path.join(self.pluginConfig[SETTING_DIR], uuid.uuid1().__str__())
        ret = "%s.terminatorExport" % filename
        if self.pluginConfig[SETTING_EXPORT_FILE] != "":
            with open(self.pluginConfig[SETTING_EXPORT_FILE], "a") as targetFile:
                targetFile.writelines(ret + "\n")
                targetFile.close()
        
        return ret