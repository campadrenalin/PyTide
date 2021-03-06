#           Licensed to the Apache Software Foundation (ASF) under one
#           or more contributor license agreements.  See the NOTICE file
#           distributed with this work for additional information
#           regarding copyright ownership.  The ASF licenses this file
#           to you under the Apache License, Version 2.0 (the
#           "License"); you may not use this file except in compliance
#           with the License.  You may obtain a copy of the License at

#             http://www.apache.org/licenses/LICENSE-2.0

#           Unless required by applicable law or agreed to in writing,
#           software distributed under the License is distributed on an
#           "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#           KIND, either express or implied.  See the License for the
#           specific language governing permissions and limitations
#           under the License. 

import webgui
import json
import re
import webbrowser

from gui import rel_to_abs

withcontact = re.compile("with[ :](\S*)")
pageregex = re.compile(" ?::(\d+)")

def getContactsFromQuery(query):
	return withcontact.findall(query)

def getPageFromQuery(query, page):
	''' returns (query, page) '''
	pgs = pageregex.search(query)
	if pgs != None:
		page = int(pgs.group(1))-1
		query = pageregex.sub("",query)
	return (query, page)

class WaveList(webgui.browserWindow):
	def __init__(self,registry):
		webgui.browserWindow.__init__(self,rel_to_abs("gui/html/wavelist.html"),registry, echo=False)
		self.options = {}
		self.ready = False
		self.getConfig('tbshorten')
		self.getConfig('autorefresh_rate')

	def process(self, data):
		''' Recieve UI input data from window '''
		if data != None:
			print data
			if data['type'] == 'query':
				if 'page' in data:
					self.query(data['value'], page=data['page'])
				else:
					self.query(data['value'])
			elif data['type'] == 'sendHTML':
				print data['html']
			elif data['type'] == 'getOptions':
				# Send a dict of all set options
				self.send("pushOptions(%s)" % json.dumps(self.options))
			elif data['type'] == 'setOption':
				# pass on data to other windows and save to config
				self.setConfig(data['key'],data['value'])
			elif data['type'] == 'Open':
				self.openWaves(data['addresses'])
			elif data['type'] == 'waveSelected':
				self.registry.msgAll(data)
			self.ready = True
		else:
			return None

	def regmsg_receive(self, data):
		''' Recieve message from registry. '''
		if 'type' in data:
			if data['type'] == 'setOption':
				self.options[data['name']] = data['value']
				self.send("pushOption('%s',%s)" % (data['name'],data['value'].lower()))
			elif data['type'] == 'waveSelected':
				self.send("setWaveSelected('%s',%s)" % (data['id'],str(data['value']).lower()))
			elif data['type'] == 'newWaveList' or data['type'] == 'newWaveViewer':
				self.send('sendSelectedWaves()');
			elif data['type'] == 'kill':
				self.close()
				
		print "Reg >> Wavelist: ",data

	@staticmethod
	def escape(str):
		return str.replace('"','\"')

	def getTitleFromQuery(self, querytext):
		''' Pretty self-explanatory. Takes in a query, returns the appropriate window title for it.'''
		if querytext == "in:inbox":
			return "Inbox"
		elif querytext == "in:all":
			return "Archive"
		elif querytext == "::contacts":
			return "Contacts"
		else: return 'Search "%s"' % querytext

	def query(self, query, page=0):
		'''Send a query to the Network, get a list of results back, and 
		pass it on to the window.'''

		if query == "": 
			query="in:inbox"
		query, page = getPageFromQuery(query, page)
		if "::contacts" in query:
			def callback(contactList):
				self.send("clearList()")
				self.showContacts(contactList, True)
				self.send("pullSelection(); checkSelect()")
			self.registry.Network.getContacts(callback, self.loaderror)
			return

		# check for WITH keywords and make a microquery for them
		addresses = getContactsFromQuery(query)
		if addresses != []:
			def callback(contactList):
				self.send("clearList()")
				self.showContacts(contactList, False)
				self.registry.Network.query(self.recv_query, query, startpage=page)
			self.registry.Network.getContacts(callback, self.loaderror)
		else:
			def callback(items):
				self.send("clearList()")
				self.recv_query(items)
				self.send("pullSelection(); checkSelect()")
			self.registry.Network.query(callback, query, startpage=page, errcallback=self.loaderror)

	def recv_query(self, results):
		'''Receive a loaded query from the Network'''
		if results.page!=0:
			pagetext = ", Page "+str(results.page+1)
		else: pagetext = ""
		if results == None:
			self.send("setError('connection')")
			return
		totalunread = 0
		print results.page, "/", results.maxpage, "\t",results.num_results
		jres = {'query':self.escape(results.query),'digests':[],'page':results.page,'maxpage':results.maxpage}
		for digest in results.digests:
			plist = digest.participants.serialize()
			participants = [self.registry.Network.participantMeta(x) for x in plist]
			print digest.waveid
			if digest.unread_count != 0:
				totalunread += 1
			jres['digests'].append({
				'title':self.escape(digest.title),
				'participants':participants,
				'unread':digest.unread_count,
				'total':digest.blip_count,
				'date':digest.date,
				'location':digest.waveid
				})
		if totalunread != 0:
			pagetext += " (%d)" % totalunread
		self.setTitle(self.getTitleFromQuery(results.query)+pagetext)
		self.send("reloadList(%s, true)" % json.dumps(jres))
		self.send("pullSelection(); checkSelect()")

	def loaderror(self, e):
		self.send("clearList(); setError('connection'); checkSelect()")

	def showContacts(self, contactlist, useLongEnd):
		contacts = [{'name':c.name or c.nick,'address':c.addr,'avatar':c.pict} for c in contactlist]
		self.send("contactsList(%s,%s)" % (json.dumps(contacts),str(useLongEnd).lower()))

	def getConfig(self,key):
		self.options[key] = self.registry.getWaveListConfig(key)
		if self.ready:
			self.send('pushOption("%s","%s")' % (key,self.options[key]))

	def setConfig(self,key, value=None):
		if value != None:
			self.options[key]=value
		self.registry.setWaveListConfig(key, self.options[key])

	def openWaves(self, idlist):
		''' Open a list of waves. In current implementation,
		opens up to two waves in Google Wave interface, with
		waves 3-n minimized.'''
		url = 'https://wave.google.com/wave/?nouacheck#'
		if len(idlist) > 1:
			url+="minimized:search,"
		for i, id in enumerate(idlist):
			if i > 0:
				url += ","
			if i < 2:
				url += "restored:wave:"
			else:			
				url += "minimized:wave:"
			url += id
		webbrowser.open(url)
