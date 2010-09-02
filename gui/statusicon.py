import gtk
import time

class StatusIcon(gtk.StatusIcon):
	def __init__(self, registry):
		gtk.StatusIcon.__init__(self)
		self.set_from_file("gui/html/img/something.jpg")
		self.registry = registry
		self.connect('popup-menu', self.on_right_click)
		self.connect('activate', self.on_left_click)
		gtk.main()

	def popupMenu(self, event_button, event_time, itemList=None):
		# Create and show the popup menu
		menu = gtk.Menu()

		for item in itemList:
			if len(item)==3:
				menuItem = gtk.MenuItem(item[0])
				menu.append(menuItem)
				menuItem.connect_object("activate",item[1],item[2])
				menuItem.show()
			else:
				# seperator
				menuItem = gtk.MenuItem()
				menu.append(menuItem)
				menuItem.show()
		menu.show()
		menu.popup(None, None, gtk.status_icon_position_menu, event_button, event_time,self)

	def on_right_click(self,data,event_button,event_time):
		allwins = self.registry.getAllWindows()
		openlist = []
		optionlist = []
		for win in allwins:
			openlist.append((win.getTitle(),self.focusWin,win))
		if openlist != []:
			openlist.append(())
		if self.registry.Network.is_connected():
			optionlist += [
				('New WaveList window',self.newWaveList,None)]
		else:
			login = self.registry.Network.loginWindow
			openlist.append((login.getTitle(),self.focusWin,login))

		self.popupMenu(event_button, event_time, openlist+optionlist+[('Quit',self.quit, None)] )

	def on_left_click(self,icon):
		if self.registry.Network.is_connected():
			popuplist = [('No updates',self.blank,None)]
		else:
			popuplist = [("You're not logged in.",self.blank,None)]
		self.popupMenu(1, gtk.get_current_event_time(),popuplist)

	def focusWin(self, data=None):
		if data != None:
			data.focus()

	def quit(self, data=None):
		gtk.main_quit()

	def newWaveList(self, data=None):
		self.registry.newWaveList()

	def blank(self, data=None):
		pass