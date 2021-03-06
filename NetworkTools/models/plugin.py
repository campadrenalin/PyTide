#
# Copyright Notice:
#
# Copyright 2010    Nathanael Abbotts (nat.abbotts@gmail.com),
#                   Philip Horger,
# 
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

from multiprocessing import Process, Queue
from Queue import Empty, Full
from threading import Lock
from threads import LoopingThread

class Responder(LoopingThread):
    ''' A class used by the Plugin core to process the outqueue '''
    def __init__(self, plugin):
        super(Responder,self).__init__(speed=.1)
        self.plugin = plugin

    def process(self):
        try:
            res = self.plugin.outqueue.get_nowait()
            self.plugin.popcallback(res)(res[1])
        except Empty:
            pass

class Plugin(Process):
    ''' Contains a process that handles messages and pushes some back. '''
    def __new__(cls, *args, **kwargs):
        self = super(Plugin, cls).__new__(cls)
        super(Plugin, self).__init__()
        self.daemon = True
        self.inqueue = Queue()
        self.outqueue = Queue()
        self.callbacks = {}
        self.maxcallback = 0
        self.cblock = Lock()
        self.responder = Responder(self)
        self.responder.start()
        return self
    def __init__(self, *args, **kwargs):
        """__init__ should be overridden, but to prevent misplaced super( )
        calls, a placeholder __init__ has been put in place."""
        print "Erronious super call detected! (harmless)"
        
    def run(self):
        ''' Repeatedly process items in queue '''
        while 1:
            try:
                self.process(self.inqueue.get(True, 0.01))
            except Empty:
                pass

    def process(self, data):
        ''' Process a piece of data. All data is in dict form.

        "contacts" is a request for the full list of the user's contacts.

        "me" is a request for the users own information.
        The callback takes a models.user.User
        '''
        if type(data).__name__ != 'dict':
            return False
        t = data['type']
        try:
            if t == 'query':
                self.output(data, self._query(data['query'],data['page']))
            elif t == 'contacts':
                self.output(data, self._contacts())
            elif t == 'me':
                self.output(data, self._me())
            elif t == 'submit':
                self.output(data, self._submit_wavelet(data['wavelet']))
        except Exception as e:
            self.error(data, e)

    def output(self, data, result):
        self.outqueue.put((data['callback'], result))

    def pushcallback(self, c):
        self.cblock.acquire()
        self.callbacks[self.maxcallback]=c
        self.maxcallback += 1
        self.cblock.release()
        return self.maxcallback-1

    def popcallback(self, data):
        self.cblock.acquire()
        c = self.callbacks[data[0]]
        del self.callbacks[data[0]]
        self.cblock.release()
        return c

    def query(self, query, startpage, callback, errorcallback):
        ''' Callback function takes a models.digest.SearchResults '''
        self.inqueue.put({'type':'query',
                'query':query,
                'page':startpage,
                'callback':self.pushcallback(callback),
                'ecallback':self.pushcallback(errorcallback),
                })

    def get_contacts(self, callback, errorcallback):
        ''' Callback function takes a list of models.user.User '''
        self.inqueue.put({'type':'contacts',
                'ecallback':self.pushcallback(errorcallback),
                'callback':self.pushcallback(callback)})

    def get_me(self, callback, errorcallback):
        ''' Callback function takes a models.user.User '''
        self.inqueue.put({'type':'me',
                'ecallback':self.pushcallback(errorcallback),
                'callback':self.pushcallback(callback)})

    def submit_wavelet(self, wavelet, callback, errorcallback):
	''' Callback function takes a (wave_id, wavelet_id) tuple '''
	self.inqueue.put({'type':'submit',
		'wavelet':wavelet,
                'ecallback':self.pushcallback(errorcallback),
                'callback':self.pushcallback(callback)})

    def _query(self, query, startpage):
        ''' Override me! Return a models.digest.SearchResults '''
        pass

    def _contacts(self):
        ''' Override me! Return a list of models.user.User '''
        pass

    def _me(self):
        ''' Override me! Return a models.user.User '''
        pass

    def _submit_wavelet(self, wavelet):
	''' Override me! Return a (wave_id, wavelet_id) tuple '''
	pass

    def error(self, data, e):
        self.outqueue.put((data['ecallback'], e))
