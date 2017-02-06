#! /usr/bin/env python2.6
# -*- coding: utf-8 -*-

"""
Author: GlennNZ

"""

import datetime
import time as t
import urllib2
import os
import shutil
import json
import logging
import threading
from operator import itemgetter

from ghpu import GitHubPluginUpdater

try:
    import indigo
except:
    pass

# Establish default plugin prefs; create them if they don't already exist.
kDefaultPluginPrefs = {
    u'configMenuPollInterval': "300",  # Frequency of refreshes.
    u'configMenuServerTimeout': "15",  # Server timeout limit.
    # u'refreshFreq': 300,  # Device-specific update frequency
    u'showDebugInfo': False,  # Verbose debug logging?
    u'configUpdaterForceUpdate': False,
    u'configUpdaterInterval': 24,
    u'updaterEmail': "",  # Email to notify of plugin updates.
    u'updaterEmailsEnabled': False  # Notification of plugin updates wanted.
}


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"logLevel"])
        except:
            self.logLevel = logging.INFO

        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))

        self.debugLog(u"Initializing plugin.")
        self.andTimers = False
        self.updater = GitHubPluginUpdater(self)
        self.configUpdaterInterval = self.pluginPrefs.get('configUpdaterInterval', 24)
        self.configUpdaterForceUpdate = self.pluginPrefs.get('configUpdaterFUpdate', False)
        self.folderLocation = self.pluginPrefs.get('folderLocation', '')
        self.scheduleExclude = self.pluginPrefs.get('scheduleExclude','')
        self.hoursCheck = self.pluginPrefs.get('hoursCheck','24')
        if self.folderLocation == '':
            self.logger.info(u'Folder Name cannot be empty')
            return

    def __del__(self):
        self.debugLog(u"__del__ method called.")
        indigo.PluginBase.__del__(self)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:

            self.debugLog(u"User prefs saved.")


        return True

    def saveData(self, pluginAction):
        self.debugLog(u'Save Data Called')
        self.saveSchedule(pluginAction)
        self.saveTimers(pluginAction)


    def saveTimers(self):

        currentState = self.getTimerVariable()

        if currentState == "paused":
            self.debugLog(u'Timers Already Paused - cannot rerun')
            return


        self.variableTimeraction("paused")

        self.debugLog(u'loadTimers Current State:' + unicode(currentState))

        self.debugLog(u'savedTimers called')
        timersDict = {}
        timersDict['control']= 'save'
        timersDict['controlTime'] = t.time()


        tId = "com.perceptiveautomation.indigoplugin.timersandpesters"
        timerPlugin = indigo.server.getPlugin(tId)
        #if timerPlugin.isEnabled():

        for timers in indigo.devices.iter():
            if timers.pluginId==tId and timers.states['timerStatus']=='active':
                self.debugLog(unicode(timers.name))
                timersDict[str(timers.id)] = "wasActiveNowPaused"
                timerPlugin.executeAction("pauseTimer", deviceId=timers.id)
                self.debugLog(unicode('Timer:')+unicode(timers.name)+unicode(" is now Paused."))

        self.debugLog(unicode(timersDict))
        try:
            folder = self.folderLocation
            filename = "timersSave.json"
            with open(folder+filename, 'w') as fp:
                json.dump(timersDict, fp)
        except Exception as error :
            self.debugLog(u'Saving Error '+unicode(error))
            self.andTimers = False

        self.andTimers = False


    def variableaction(self, action):


        self.debugLog(u'variableaction called with action:'+unicode(action))
        if not ('ScheduleCatchUP' in indigo.variables.folders):
            #create folder
            folderId = indigo.variables.folder.create('ScheduleCatchUP')
            folder = folderId.id
        else:
            folder = indigo.variables.folders.getId('ScheduleCatchUP')

        if not ('ScheduleCatchUPState' in indigo.variables):
            newVar = indigo.variable.create('ScheduleCatchUPState', str(action), folder)
        else:
            indigo.variable.updateValue('ScheduleCatchUPState', str(action))

        return

    def variableTimeraction(self, action):


        self.debugLog(u'variableTimer action called with action:'+unicode(action))
        if not ('ScheduleCatchUP' in indigo.variables.folders):
            #create folder
            folderId = indigo.variables.folder.create('ScheduleCatchUP')
            folder = folderId.id
        else:
            folder = indigo.variables.folders.getId('ScheduleCatchUP')

        if not ('ScheduleCatchUPTimerState' in indigo.variables):
            newVar = indigo.variable.create('ScheduleCatchUPTimerState', str(action), folder)
        else:
            indigo.variable.updateValue('ScheduleCatchUPTimerState', str(action))

        return


    def getVariable(self):

        self.debugLog(u'get the variable called')
        newVar ="none"

        if not ('ScheduleCatchUP' in indigo.variables.folders):
            return "none"

        if not ('ScheduleCatchUPState' in indigo.variables):
            return "none"
        else:
            newVar = indigo.variables['ScheduleCatchUPState'].value

        return newVar

    def getTimerVariable(self):

        self.debugLog(u'get Timer variable called')
        newVar ="none"

        if not ('ScheduleCatchUP' in indigo.variables.folders):
            return "none"

        if not ('ScheduleCatchUPTimerState' in indigo.variables):
            return "none"
        else:
            newVar = indigo.variables['ScheduleCatchUPTimerState'].value

        return newVar

    def saveSchedule(self):

        currentState = self.getVariable()
        self.debugLog(u'Current State:'+unicode(currentState))

        if currentState == "loading":
            self.debugLog(unicode("Already loading schedule.  Cannot Save."))
            return


        self.variableaction("saving")

        self.debugLog(u'Save Schedule called')
        scheduleExclude = self.pluginPrefs.get('scheduleExclude', '')
        schedule = {}
        # add control key as to what is happening to avoid running when saving
        schedule['control'] = 'save'
        # Current time in epoc of saving
        schedule['controlTime'] = t.time()

        for sch in indigo.schedules.iter():
            if sch.enabled:
                #self.debugLog(unicode(sch.id))
                if unicode(sch.id) not in scheduleExclude:
                    #Save due schedule in Epoc time - less readable, more json, easier to sort by
                    schedule[str(sch.id)] = t.mktime(sch.nextExecution.timetuple())

        # Save Schedules
        self.debugLog(unicode(schedule))
        try:
            folder = self.folderLocation
            filename = "scheduleSave.json"
            with open(folder+filename, 'w') as fp:
                json.dump(schedule, fp)
        except Exception as error :
            self.debugLog(u'Saving Error '+unicode(error))

        self.sleep(10)
        self.variableaction("ready")
        if self.andTimers:
            self.saveTimers()

    def allActions(self,pluginAction):


        self.debugLog(u'all Actions called and progressing action')
        #self.debugLog(unicode(pluginAction))
        currentState = self.getVariable()
        action = pluginAction.pluginTypeId
        self.debugLog(unicode("Threading:") + unicode(threading.currentThread().getName()))
        self.debugLog(unicode("Threading Count:") + unicode(threading.activeCount()))

        if currentState != "ready":
            self.debugLog(u'Not Ready: State:'+unicode(currentState)+"  Returning without action.")
            return

        if action == "SaveScheduleTimers":
            self.andTimers = True
        if action == "LoadScheduleTimers":
            self.andTimers = True

        if action == "LoadSchedule" or action == "LoadScheduleTimers":
            # START AS NEW THREAD AND ONLY ALLOW ONE THREAD
            t = threading.Thread(target=self.loadSchedule)
            t.start()
            #self.loadSchedule(pluginAction)
            return

        if action == "SaveSchedule" or action == "SaveScheduleTimers":
            t = threading.Thread(target=self.saveSchedule)
            t.start()
            return


        return


    def loadSchedule(self):


        self.debugLog(u'Load Schedule called')

        hoursCheck = self.pluginPrefs.get('hoursCheck', '24')

        currentState = self.getVariable()
        self.debugLog(u'Current State:'+unicode(currentState))

        if currentState == "loading":
            self.debugLog(unicode("Already loading schedule....."))
            return

        self.variableaction("loading")

        schedule = {}
        try:
            folder = self.folderLocation
            filename = "scheduleSave.json"
            with open(folder+filename, 'r') as fp:
                schedule = json.load(fp)

        except Exception as error :
            self.debugLog(u'Loading Error '+unicode(error))

        self.debugLog(unicode(schedule))


        try:
            #schedule['uitimeSaved'] = t.strftime('%Y-%m-%d %H:%M:%S', t.localtime(schedule['controlTime']))
            #schedule['uicurrentTime'] =  t.strftime('%Y-%m-%d %H:%M:%S', t.localtime(t.time()))
            self.logger.debug(u'Schedule Loaded')
            self.logger.debug(unicode(schedule))
            # Check for missing schedules
            # hoursCheck * 60 * 60  = epoc time difference
            # sort by time/value in schedule list


            currentTime = t.time()
            epocDifference = float(hoursCheck) * 60 * 60

            currentTime = float(currentTime)

            timesaved = float(schedule['controlTime'])

            endTime = timesaved + epocDifference

            self.debugLog(u'checkTime:'+unicode(currentTime))
            self.debugLog(u'endTime:'+unicode(endTime))
            self.debugLog(u'epocDifference:'+unicode(epocDifference))

            for key, value in sorted(schedule.iteritems(), key=lambda (k, v): (v, k)):
                #self.debugLog(unicode("%s: %s" % (key, value)))
                if key != "control" and key != "controlTime":
                    if value < currentTime and value < endTime:
                        #self.debugLog(unicode("%s: %s" % (key, value)))
                        self.debugLog(unicode("Current value:")+unicode(value)+unicode(" and currentTime:")+unicode(currentTime)+unicode(" and endTime:")+unicode(endTime))
                        try:
                            self.logger.info(unicode('Schedule:')+unicode(indigo.schedules[long(key)].name)+unicode(' Should have already Happened.'))
                            self.logger.info(u'Executing Schedule:'+unicode(indigo.schedules[long(key)].name))

                            indigo.schedule.execute(long(key))
                            self.sleep(5)
                        except Exception as error:
                            self.debugLog(u'executing schedule issue. ? Item no longer exists')
                            self.debugLog(unicode(error))

        except Exception as error :
            self.debugLog(u'Exceuting Schedule Error '+unicode(error))

        self.debugLog(unicode("tidying up.."))
        self.sleep(5)

        #resave file with updating control ie. done
        self.variableaction("ready")

        if self.andTimers:
            self.debugLog(u'Running Timers Loading...')
            self.loadTimers()


    def loadTimers(self):
        self.debugLog(u'Load Timers called')
        currentState = self.getTimerVariable()




        self.debugLog(u'loadTimers Current State:'+unicode(currentState))


        hoursCheck = self.pluginPrefs.get('hoursCheck', '24')
        tId = "com.perceptiveautomation.indigoplugin.timersandpesters"
        timerPlugin = indigo.server.getPlugin(tId)
        timersDict = {}
        try:
            folder = self.folderLocation
            filename = "timersSave.json"
            with open(folder + filename, 'r') as fp:
                timersDict = json.load(fp)

        except Exception as error:
            self.debugLog(u'Loading loadTimers Error ' + unicode(error))
            self.andTimers = False

        self.debugLog(u'timers loaded')
        self.debugLog(unicode(timersDict))
        self.variableTimeraction("ready")

        try:
            timersDict['control'] = "load"
            for key, value in timersDict.iteritems():
                if key != "control" and key !="controlTime":
                    self.debugLog( unicode("Timer: Id:")+ unicode(key) )
                    timerPlugin.executeAction("resumeTimer", deviceId=long(key))

        except Exception as error:
            self.debugLog(u'loadTmers Error '+unicode(error))
            self.andTimers = False

        self.andTimers = False
        self.variableTimeraction("ready")




    def uiScheduleList(self, filter="", valuesDict=None, typeId="", targetId=0) :

        theList = []
        for sch in indigo.schedules.iter():
            if sch.enabled:
                theList.append((unicode(sch.id),unicode(sch.name)))
        return theList


    # Start 'em up.
    def deviceStartComm(self, dev):

         self.debugLog(u"deviceStartComm() method called.")


    # Shut 'em down.
    def deviceStopComm(self, dev):

        self.debugLog(u"deviceStopComm() method called.")
        indigo.server.log(u"Stopping device: " + dev.name)

    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    def checkForUpdates(self):
        if self.updater.checkForUpdate() == False:
            indigo.server.log(u"No Updates are Available")

    def updatePlugin(self):
        self.updater.update()


    def shutdown(self):

         self.debugLog(u"shutdown() method called.")

    def startup(self):

        self.debugLog(u"Starting Plugin. startup() method called.")

        # See if there is a plugin update and whether the user wants to be notified.
        try:
            if self.configUpdaterForceUpdate:
                self.updatePlugin()

            else:
                self.checkForUpdates()
            self.sleep(1)
        except Exception as error:
            self.errorLog(u"Update checker error: {0}".format(error))

    def validatePrefsConfigUi(self, valuesDict):

        self.debugLog(u"validatePrefsConfigUi() method called.")

        error_msg_dict = indigo.Dict()

        if valuesDict[u'folderLocation'] == '':

            error_msg_dict[u'folderLocation']=u'Folder Location Cannot be blank'
            return (False, valuesDict,error_msg_dict)



        return True, valuesDict


    def toggleDebugEnabled(self):
        """
        Toggle debug on/off.
        """

        self.debugLog(u"toggleDebugEnabled() method called.")
        if self.logLevel == logging.INFO:
             self.logLevel = logging.DEBUG

             self.indigo_log_handler.setLevel(self.logLevel)
             indigo.server.log(u'Set Logging to DEBUG')
        else:
            self.logLevel = logging.INFO
            indigo.server.log(u'Set Logging to INFO')
            self.indigo_log_handler.setLevel(self.logLevel)

        self.pluginPrefs[u"logLevel"] = self.logLevel
        return
