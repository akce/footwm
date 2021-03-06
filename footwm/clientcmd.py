"""
Client window commands.

Copyright (c) 2016 Akce
"""

import types

from . import display
from . import log as logger
from . import window

log = logger.make(name=__name__)

class ClientCommand:
    """ Higher level X client commands. They will interpret things like indexes etc. """
    def __init__(self, root):
        self.root = root

    @property
    def activewindow(self):
        return self.root.activewindow

    def activatewindow(self, stacking=True, index=None, window=None):
        """ Send an EWMH _NET_ACTIVE_WINDOW message to the window manager. """
        # TODO account for window desktop. Either switch to desktop, or ignore request.
        win = self._getwindow(stacking=stacking, index=index, window=window)
        if win:
            log.debug("0x%08x: activatewindow index=%s win=%s", win.window, index, win)
            self.root.activewindow = win

    def closewindow(self, stacking=True, index=None, window=None):
        """ Send an ICCCM WM_DELETE_WINDOW message to the window. """
        win = self._getwindow(stacking=stacking, index=index, window=window)
        if win:
            log.debug("0x%08x: closewindow index=%s win=%s", win.window, index, win)
            self.root.closewindow(win)

    def setwindowdesktop(self, desktopindex, stacking=True, index=None, window=None):
        win = self._getwindow(stacking=stacking, index=index, window=window)
        if win:
            log.debug("0x%08x: setwindowdesktop desktop=%d index=%s", win.window, desktopindex, index)
            self.root.setwindowdesktop(win, desktopindex)

    def adddesktop(self, name, index):
        self.root.adddesktop(name, index)

    def deletedesktop(self, index):
        self.root.deletedesktop(index)

    def renamedesktop(self, index, name):
        self.root.renamedesktop(index, name)

    def selectdesktop(self, index):
        self.root.currentdesktop = index

    def getdesktopnames(self):
        return self.root.desktopnames

    @property
    def currentdesktop(self):
        return self.root.currentdesktop

    def getwindowlist(self, stacking=True):
        # Filter on desktop since stacklist has all windows.
        # XXX Optionally turn off desktop filter?
        desktop = self.root.currentdesktop
        winlist = self.root.clientliststacking if stacking else self.root.clientlist
        return [w for w in winlist if w.desktop == desktop]

    def _getwindow(self, window=None, index=None, stacking=True):
        """ Return window selected by window (id) or index. The index
        is then either based on stacking or creation order depending
        on whether stacking is True. """
        if index is not None:
            try:
                win = self.getwindowlist(stacking)[index]
            except IndexError:
                win = None
        elif window is not None:
            win = self.root.children[window]
            assert win.window == window
        else:
            # internal error!
            win = None
        return win

    def startlogging(self, modulenames, levelname, outfilename):
        self.root.startlogging(modulenames=modulenames, levelname=levelname, outfilename=outfilename)

    def stoplogging(self):
        self.root.stoplogging()

def makedisplayroot(displayname=None):
    displayobj = display.Display(displayname)
    log.debug('Connect name=%s display=%s', displayname, displayobj)
    root = window.ClientRoot(displayobj, displayobj.defaultrootwindow)
    return displayobj, root
