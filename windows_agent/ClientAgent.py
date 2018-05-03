import servicemanager
import socket
import sys
import win32event
import win32service
import win32serviceutil
import platform
import wmi
import pythoncom
import datetime

import win32evtlogutil
import uuid
import http.client
import urllib.parse
import json
import hashlib

from winreg import *

TIMEOUT = 0.5
SALT = "29"

def writeLog(appname, message, error=False):
    # message - итерируемый объект (например, кортеж строк)
    type_message = 1 if error else 0
    win32evtlogutil.ReportEvent(appname,
                                0,
                                0,  
                                type_message,  # 0 - info, 1 - error
                                message)    
        
    
def sendInfo(appname, addr, params):
    max_attempt = 5
    cur_attempt = 1
    conn = None
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    while cur_attempt <= max_attempt:
        try:
            cur_attempt += 1
            conn = http.client.HTTPConnection(addr, timeout=1)
            conn.request("POST", "/", json.dumps(params), headers)
            response = conn.getresponse()
            status = response.status
            conn.close()
            return status
        except:
            continue
    if conn is not None:
        conn.close()
    msg = ('Error send data to Server Agent', )
    writeLog(appname, msg, True)
    

class SystemInfo(object):
    
    def __init__(self, appname):
        pythoncom.CoInitialize()
        self._appname = appname
        self._host = platform.node()
        self._wmi = wmi.WMI(self._host)
        self._starttime = datetime.datetime.now()
        self._endtime = ""
        self._logintime = ""
        self._logofftime = ""
        self._lastuser = ""
        self._user = ""
        self._domain = self.get_domain()
        self._ip = self.local_ip()
        self._uid = ""
        self._versionOS = ""
        self._error = False
        self._server = {'addr': "", 'port': ""}
        self._stopped = False
        self.start()
    
    @property
    def config_error(self):
        return self._error
    
    def start(self):
        if not self.read_regConfig():
            msg =('Cannot read config', )
            writeLog(self._appname, msg, True)  
            return 
        msg = ['Agent start: {0}'.format(self._starttime.strftime("%Y-%m-%d %H:%M:%S")), 
               'HOSTNAME: {0}'.format(self._host), 
               'IP: {0}'.format(self._ip), 
               'UID: {0}'.format(self._uid), 
               'Domain: {0}\n'.format(self._domain), 
               '{0}:{1} {2}\n'.format(self._server['addr'], self._server['port'], self._versionOS),
               ]  
        
        writeLog(self._appname, msg)
        # push to server agent [event='start']
        addr, params = self.prepare_send('start') 
        sendInfo(self._appname, addr, params)
        
    def stop(self):
        if not self._stopped:
            self._stopped = True
            self._endtime = datetime.datetime.now()
            # push to server agent [event='stop']
            addr, params = self.prepare_send('stop') 
            sendInfo(self._appname, addr, params)        
            msg = ('Agent stop: {0}'.format(self._endtime.strftime("%Y-%m-%d %H:%M:%S")), )
            writeLog(self._appname, msg)        
        
    def get_domain(self):
        try:  
            for s in self._wmi.Win32_ComputerSystem():
                return s.Domain
        except:
            return ""      
    
    def get_username(self):
        try:  
            for s in self._wmi.Win32_ComputerSystem():
                tmp = s.UserName.split('\\')
                if len(tmp) > 1:
                    return tmp[-1]
        except:
            return ""

   
    def read_regConfig(self):
        try:
            regpath = "SOFTWARE\SoshWFE"
            key = OpenKey(HKEY_LOCAL_MACHINE, regpath)
            # параметры подключения к серверному агенту
            self._server = {'addr': QueryValueEx(key, "serverIp")[0], 
                            'port': QueryValueEx(key, "serverPort")[0]}
            # версия нашей сборки операционной системы
            self._versionOS = QueryValueEx(key, "versionSystem")[0]
            try:
                # uid может и не быть в реестре
                self._uid = QueryValueEx(key, "uid")[0]
            except FileNotFoundError:
                # если uid нет, то используем мак-адрес
                self._uid = uuid.getnode()
            CloseKey(key)    
            return True
        except:
            self._error = True
            CloseKey(key)
            return False
        
        
    def local_ip(self):
        return socket.gethostbyname(socket.getfqdn())
    
    def update(self):
        self._user = self.get_username()
        if self._user != self._lastuser:               
            if self._user:
                self._logintime = datetime.datetime.now()
                self._logofftime = ""  
                addr, params = self.prepare_send('login')
                msg = ('Log In: {0}\n'.format(self._user), )
            else:
                self._logofftime = datetime.datetime.now()
                addr, params = self.prepare_send('logoff') 
                self._logintime = ""
                # self._logofftime = ""
                msg = ('Log Off: {0}\n'.format(self._lastuser), )
                
            self._lastuser = self._user
            sendInfo(self._appname, addr, params)            
            writeLog(self._appname, msg)
        else:
            addr, params = self.prepare_send('state')
            sendInfo(self._appname, addr, params) 
            
    def prepare_send(self, event):
        params = {'event': event, 'uid':self._uid, 'hostname' : self._host, 
                  'localip': self._ip, 'version': self._versionOS, 'domain': self._domain, 
                  'starttime': self._starttime.timestamp(), 'endtime': "", 
                  'host_uptime': datetime.datetime.now().timestamp() - self._starttime.timestamp(), 
                  'username': self._user, 'logintime': "", 'logofftime': "",
                  'user_uptime': 0}
        params["token"] = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + SALT).encode("utf-8")).hexdigest()
        if event == "logoff":
            params['username'] = self._lastuser
        if self._endtime:
            params['endtime'] = self._endtime.timestamp()
            params['host_uptime'] = params['endtime'] - params['starttime']
        if self._logintime:
            params['logintime'] = self._logintime.timestamp()
            params['user_uptime'] = datetime.datetime.now().timestamp() - params['logintime']
        if self._logofftime:
            params['logofftime'] = self._logofftime.timestamp()    
            if self._logintime:
                params['user_uptime'] =  params['logofftime'] - self._logintime.timestamp()
        addr = self._server['addr'] + ":" + self._server['port']
        return addr, params
    
    
class ClientAgent(win32serviceutil.ServiceFramework):
    _svc_name_ = "Monitoring Client Agent"
    _svc_display_name_ = "Monitoring Client Agent"
    _svc_description_ = "Monitoring Agent (SCHOOL1212)"
    _svc_deps_ = ("Dhcp", "eventlog")

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.timeout = TIMEOUT * 1000 
        #socket.setdefaulttimeout(TIMEOUT)
        self.sInfo = None      
        self.seconds = 0 

    def SvcStop(self):
        if self.sInfo is not None:
            self.sInfo.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        
    def SvcShutdown(self):
        self.SvcStop()
        
    def SvcDoRun(self):
        rc = None 
        try:
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.sInfo = SystemInfo(self._svc_display_name_)
            self.sInfo.update()
            while rc != win32event.WAIT_OBJECT_0 and not self.sInfo.config_error:
                if self.seconds >= 30:
                    self.sInfo.update()
                    self.seconds = 0 
                rc = win32event.WaitForSingleObject(self.hWaitStop, self.timeout)
                self.seconds += self.timeout / 1000
            self.SvcStop()
        except:
            self.SvcStop()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ClientAgent)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ClientAgent)
