"""
Window classes for footwm.

Copyright (c) 2016 Akce

This module has windows for root and normal/transient on both the
window manager and client sides.

ie,
- WmRoot: Window manager root window operations
- WmNormal/WmTransient: Window manager operations for normal and transient windows
- ClientRoot: Root window operations for clients
- ClientWindow: Window operations for normal windows from the clients perspective.

Those main classes use inheritance of ICCCM, ewmh, and custom
mixins to build their interfaces. That way the rest of the system
communicate via the window interface, and this module handles
"delegation" to the appropriate interface..

Note that the parent classes instanciate things that the child classes need so
there is a method to the madness behind the inheritance order. New
feature classes must be added to the left-end of the inheritance
resolution order.

eg,
% python3
>>> from footwm import window
>>> window.WmRoot.mro()
[<class 'footwm.window.WmRoot'>, <class 'footwm.ewmh.WmRootMixin'>, <class 'footwm.ewmh.Base'>, <class 'footwm.window.Base'>, <class 'object'>]
>>> window.WmNormal.mro()
[<class 'footwm.window.WmNormal'>, <class 'footwm.window.WmWindow'>, <class 'footwm.window.WmWindowClientWindow'>, <class 'footwm.window.Base'>, <class 'object'>]
>>> window.WmTransient.mro()
[<class 'footwm.window.WmTransient'>, <class 'footwm.window.WmWindow'>, <class 'footwm.window.WmWindowClientWindow'>, <class 'footwm.window.Base'>, <class 'object'>]
>>> window.ClientRoot.mro()
[<class 'footwm.window.ClientRoot'>, <class 'footwm.command.ClientRootMixin'>, <class 'footwm.command.Base'>, <class 'footwm.ewmh.ClientRootMixin'>, <class 'footwm.ewmh.Base'>, <class 'footwm.window.Base'>, <class 'object'>]
>>> window.ClientWindow.mro()
[<class 'footwm.window.ClientWindow'>, <class 'footwm.window.WmWindowClientWindow'>, <class 'footwm.window.Base'>, <class 'object'>]
"""

import collections

from . import log as xlog
from . import xlib

log = xlog.make(name=__name__)

class WindowError(Exception):
    pass

def centregeom(geom, availablegeom):
    """ A new geometry such that the x,y coords centre the geom.width/height in the availablegeom. """
    # XXX TODO
    return geom

def fixedgeom(currentgeom, availablegeom, sizehints):
    try:
        mingeom = sizehints.mingeom
        maxgeom = sizehints.maxgeom
    except AttributeError:
        geom = None
    else:
        if mingeom == maxgeom:
            geom = mingeom
        else:
            geom = None
    return geom

def honourablemaxsizer(currentgeom, availablegeom, sizehints):
    """ Honourable max sizer tries to maximise the window but honours sizehints while doing it. """
    size = None
    if sizehints.flags.value == xlib.SizeFlags.PSize:
        # Seems to be set when the window is already at the correct size.
        size = centregeom(currentgeom, availablegeom)
    if size is None:
        # Check for windows that can't be resized, ie, min == max.
        size = fixedgeom(currentgeom, availablegeom, sizehints)
    if size is None:
        # For now, we just set to the whole available geometry.
        # TODO implement aspect, size increments, and respect for min/max constraints.
        size = availablegeom
    return size

def brutalmaxsizer(currentgeom, availablegeom, sizehints):
    """ Brutal maxsizer sets the geometry to the maximum available space, irrespective of sizehints. """
    return availablegeom

def transientsizer(currentgeom, availablegeom, sizehints):
    """ Transient sizer centres position in the available geometry but width/height are unchanged from sizehints. """
    # TODO just return as honourable max sizer.
    return honourablemaxsizer(currentgeom, availablegeom, sizehints)

class BaseWindow(object):

    def __init__(self, display, window):
        self.display = display
        self.window = window
        try:
            self.override_redirect, self.geom, self.map_state = self.display.getwindowattributes(self.window)
        except (TypeError, ValueError) as e:
            raise WindowError('0x%08x: getwindowattributes failed %s', self.window.window, e)
        self.name = self.wm_name

    def manage(self, eventmask):
        # watch, maintain, manage, control etc.
        self.display.selectinput(self, eventmask)

    @property
    def wm_name(self):
        #log.debug('0x%08x: Get WM_NAME name=%s status=%d', self.window, name)
        return self.display.getwmname(self)

    def __str__(self):
        args = [
                'id=0x{:08x}'.format(self.window),
                'name="{}"'.format(self.name),
                str(self.geom),
                'mapstate={}'.format(self.map_state),
                ]
        # XXX Should abstract this better...
        try:
            if self.res_name:
                args.append('res_name="{}"'.format(self.res_name))
        except AttributeError:
            pass
        try:
            if self.res_class:
                args.append('res_class="{}"'.format(self.res_class))
        except AttributeError:
            pass
        try:
            protocols = self.wm_protocols
        except AttributeError:
            pass
        else:
            if protocols:
                args.append('wm_protocols={}'.format(str(protocols)))
        try:
            if self.transientfor:
                args.append('transientfor=0x{:08x}'.format(self.transientfor.window))
        except AttributeError:
            pass
        try:
            if self.sizehints:
                args.append('sizehints={}'.format(self.sizehints))
        except AttributeError:
            pass
        try:
            # RootWindow
            if self.children:
                args.append("children=[{}]".format(' '.join('0x{:08x}'.format(x.window) for x in self.children.values())))
        except AttributeError:
            pass
        return '{}({})'.format(self.__class__.__name__, ' '.join(args))

class RootWindow(BaseWindow):

    def __init__(self, display, window):
        super().__init__(display, window)
        self._import_children()

    def newchild(self, windowid):
        """ Create a new child window. """
        window = self._make_window(windowid)
        # Add the window to our child dict.
        self.children[windowid] = window
        return window

    def _import_children(self):
        """ Import all the children of the root window, regardless of whether they have override_redirect set.
        The window manager will keep its own managed window lists. """
        self.children = collections.OrderedDict()
        for windowid in self.display.querytree(self):
            self.children[windowid] = self._make_window(windowid)

    def _make_window(self, windowid):
        """ Window object factory method.
        Will handle creating Normal, Transient managed windows. """
        transientfor = self.display.gettransientfor(windowid)
        log.debug('0x%08x: transientfor=%s', windowid, transientfor)
        if transientfor is None:
            # Regular window.
            window = NormalWindow(self.display, windowid)
        else:
            window = TransientWindow(self.display, windowid, self.children.get(transientfor, None))
        return window

class ClientWindow(BaseWindow):

    def __init__(self, display, window, sizer):
        super().__init__(display, window)
        self.sizer = sizer
        self.wantedgeom = self.geom
        wm_state = self.wm_state
        self.res_name, self.res_class = self.wm_class
        self.sizehints = self.display.getwmnormalhints(self)
        # The family of windows for a normal client window is only itself.
        self.family = [self]

    def hide(self):
        self.display.unmapwindow(self.window)

    def show(self):
        self.display.mapwindow(self)

    def focus(self):
        log.debug('0x%08x: focus', self.window)
        msg = 'WM_TAKE_FOCUS'
        try:
            self.clientmessage(msg)
        except KeyError:
            #log.debug('0x%08x: %s not supported', self.window, msg)
            self.display.setinputfocus(self, xlib.InputFocus.RevertToPointerRoot, xlib.CurrentTime)

    def _sendclientmessage(self, atom, time):
        """ Send a ClientMessage event to window. """
        ev = xlib.XClientMessageEvent()
        ev.type = xlib.EventName.ClientMessage
        ev.window = self.window
        ev.message_type = self.display.atom['WM_PROTOCOLS']
        ev.format = 32
        ev.data.l[0] = atom
        ev.data.l[1] = time
        return self.display.sendevent(self, ev)

    def clientmessage(self, msg, time=xlib.CurrentTime):
        """ Send a ClientMessage event to client.
        Will raise a KeyError if WM_PROTOCOLS does not support the msg type. """
        atom = self.wm_protocols[msg]
        status = self._sendclientmessage(atom, time)
        if status:
            log.debug('0x%08x: %s success', self.window, msg)
        else:
            log.error('0x%08x: %s failed', self.window, msg)

    def delete(self):
        """ Sends the WM_PROTOCOLS - WM_DELETE_WINDOW message. """
        # XXX Should we fallback to a destroy window call if this isn't supported?
        msg = 'WM_DELETE_WINDOW'
        try:
            self.clientmessage(msg)
        except KeyError:
            log.debug('0x%08x: %s not supported', self.window, msg)

    # XXX Currently unused.
    @property
    def unmapped(self):
        return self.map_state == self.map_state.IsUnmapped

    @property
    def wm_class(self):
        """ WM_CLASS is a tuple of resource name & class. See ICCCM 4.1.2.5 """
        return self.display.getclasshint(self)

    @property
    def wm_protocols(self):
        """ Return dict(name -> atom) of ATOMs comprising supported WM_PROTOCOLS for the client window. """
        return self.display.getprotocols(self)

    @property
    def wm_state(self):
        state = self.display.getwmstate(self)
        log.debug('0x%08x: Get WM_STATE state=%s', self.window, state)
        return state

    @wm_state.setter
    def wm_state(self, winstate):
        log.debug('0x%08x: Set WM_STATE state=%s', self.window, xlib.WmStateState(winstate))
        self.display.setwmstate(self, winstate)

    def resize(self, availablegeom):
        """ resize the window given the available geometry area.
        """
        # Actual geom will be set in the configure notify handler.
        self.wantedgeom = self.sizer(self.geom, availablegeom, self.sizehints)
        if self.wantedgeom != self.geom:
            log.debug('0x%08x: attempt resize %s -> %s', self.window, self.geom, self.wantedgeom)
            self.display.moveresizewindow(self, self.wantedgeom.x, self.wantedgeom.y, self.wantedgeom.w, self.wantedgeom.h)

class NormalWindow(ClientWindow):

    def __init__(self, display, window, sizer=honourablemaxsizer):
        super().__init__(display, window, sizer)

class TransientWindow(ClientWindow):

    def __init__(self, display, window, transientfor):
        super().__init__(display, window, transientsizer)
        self.transientfor = transientfor
        # The family of windows for a transient includes the parent, and potentially, that parents parents etc..
        try:
            self.family = [self] + transientfor.family
        except AttributeError:
            # transientfor may not be a managed window (?!) in which case it will be None and have no .family attribute.
            # Xwindows seems to be a land where anything goes!
            # Set the family like a normal window but we'll still draw like a transient.
            self.family = [self]