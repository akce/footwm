"""
FootKeys module.

Copyright (c) 2016 Akce
"""
# Python standard modules.
import argparse
import functools
import itertools
import operator
import os
import signal
import sys

# Local modules.
from . import clientcmd
from . import config
from . import log as logger
from . import kb
from . import nestedarg
from . import signalevent
from . import xevent
from . import xlib

log = logger.make(name=__name__)

__all__ = 'FootKeys',

def icsfactorial(modlist):
    """
    itertools.combinations factorial.

    >>> icsfactorial([1, 2])
    [(1,), (2,), (1, 2)]
    """
    def combos():
        for i in range(1, len(modlist) + 1):
            yield list(itertools.combinations(modlist, i))
    # sum flattens the list of combinations lists.
    return sum(combos(), [])

def iter2mask(iterable):
    """
    Convert an iterable to a mask.
    """
    return functools.reduce(operator.or_, iterable, 0)

class KeyAction:

    def __init__(self, key, action, requiremods=None, ignoremods=None):
        self.key = key
        self.action = action
        self.requiremods = requiremods or []
        self.ignoremods = ignoremods or []

    def __call__(self, *args, **kwargs):
        return self.action(*args, **kwargs)

class KeyBuilder:

    def __init__(self, footkeys):
        self.footkeys = footkeys
        # [KeyAction]
        self._keysymactions = []
        self._requiremods = None
        self._ignoremods = None

    def setmodifiers(self, requiremods=None, ignoremods=None):
        """ Sets global requiremods/ignoremods. """
        self._requiremods = requiremods
        self._ignoremods = ignoremods

    def addkey(self, keysym, action, requiremods=None, ignoremods=None):
        """ Adds a key/action pair to the keymap.
        requiremods & ignoremods are in addition to the global requiremods/ignoremods values.
        """
        # Don't apply the global modifiers, store them separately so we know what came from where.
        self._keysymactions.append(KeyAction(keysym, action=action, requiremods=requiremods, ignoremods=ignoremods))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # No exception occurred, install the keymap.
            self.footkeys._install(self._keysymactions, requiremods=self._requiremods, ignoremods=self._ignoremods)

class FootKeys:

    def __init__(self, displayname=None, configfilename=None):
        """
        FootKeys._handle_keypress() will apply requiremods & ignoremods to all grabbed keypresses.
        requiremods and ignoremods must be a set of footwm.xlib.KeyModifierMask values.
        All requiremods values must all be applied for a key in this keymap to match.
        All ignoremods values are all masked out and ignored in keypress events.
        """
        self.display, self.root = clientcmd.makedisplayroot(displayname)
        self.configfilename = configfilename
        def xerrorhandler(display, xerrorevent):
            log.error('X Error: %s', xerrorevent)
            return 0
        self.display.errorhandler = xerrorhandler
        self.xwatch = xevent.XWatch(self.display, self.root, self)
        self.sigwatch = signalevent.SignalsWatch(self)
        signal.signal(signal.SIGUSR1, lambda x, y: None)
        self._keycodeactions = {}

    def config(self):
        # Creating the KeyBuilder as a separate object so that the only way to
        # add keys is via a context manager. The context manager then forces
        # the call to _install the keys in the Xserver after all addkey calls
        # have been made.
        return KeyBuilder(self)

    def loadconfig(self):
        log.info('Loading config from %s', self.configfilename)
        with self.config() as keyconfig:
            # Create a client object and add it into the configs
            # namespace. One of these is handy and would be used by every
            # config.
            gl = globals().copy()
            gl['client'] = clientcmd.ClientCommand(self.root)
            gl['akce'] = functools.partial
            gl['do'] = functools.partial
            config.loadconfig(self.configfilename, gl, locals())

    def _install(self, keysymactions=None, requiremods=None, ignoremods=None):
        self._keysymactions = keysymactions
        self._requiremods = requiremods
        self._ignoremods = ignoremods
        self._rebuild()

    def uninstall(self):
        self.display.ungrabkey(xlib.AnyKey, xlib.GrabKeyModifierMask.AnyModifier, self.root)

    def _rebuild(self):
        # Reset the keycode action settings, and ungrab from Xserver.
        self.uninstall()
        self._keycodeactions = []
        # Recreate keyboard settings, this loads the keysym to keycode bindings.
        self.keyboard = kb.Keyboard(self.display)
        # Convert the keysym action objects to xserver keycodes as the xkeyboard events are given to us as keycodes.
        self._keycodeactions = self._makekeycodes()
        self._installkeycodes()
        self.display.flush()

    def _makekeycodes(self):
        keycodes = {}
        for ksa in self._keysymactions:
            # keymodifier would be a ShiftLock for capital letters, or NumLock for KP_*.
            # This keymodifier is always required for keycode.
            keycode, keymodifier = self.keyboard.keycodes[ksa.key]
            # requiremods are modifiers that are required for a key to match.
            requiremods = frozenset(([keymodifier] if keymodifier else []) + ksa.requiremods + self._requiremods)
            # ignoremods are the modifiers whose state we don't care about.
            # X requires us to explicitly register on/off states for each ignored key, hence the use of icsfactorial
            # to generate the requried combinations.
            # Note that requiremods are always removed from ignoremods.
            ignoremods = frozenset(ksa.ignoremods + self._ignoremods) - requiremods
            for mods in [()] + icsfactorial(ignoremods):
                kc = KeyAction(keycode, ksa, requiremods=requiremods.union(frozenset(mods)))
                keycodes[(keycode, iter2mask(kc.requiremods))] = kc
        return keycodes

    def _installkeycodes(self):
        """ Installs the key code actions with the x server. """
        self.root.manage(xlib.InputEventMask.KeyPress)
        for (keycode, keymodmask), keyaction in self._keycodeactions.items():
            log.debug('0x%08x: install keygrab keycode=0x%x modifier=0x%x', self.root.window, keycode, keymodmask)
            self.display.grabkey(keycode, keymodmask, self.root, True, xlib.GrabMode.Async, xlib.GrabMode.Async)

    def handle_keypress(self, e):
        """ User has pressed a key that we've grabbed. """
        # Retrieve key action and call.
        keycombo = (e.keycode, e.state.value)
        log.debug('0x%08x: handle_keypress: %s', e.window, keycombo)
        if keycombo in self._keycodeactions:
            keyaction = self._keycodeactions[keycombo]
            keyaction.action.action()
        else:
            log.error('0x%08x: no action defined for (keycode, modifier) %s', e.window, keycombo)

    def handle_mappingnotify(self, event):
        """ X server has had a keyboard mapping changed. Update our keyboard layer. """
        self._rebuild()

    def handle_signal(self, signum):
        log.debug('handle_signal called')
        if signum == signal.SIGUSR1:
            self.loadconfig()
            ret = True
        else:
            ret = False
        return ret

def getconfigfilename(configfile=None):
    return configfile or config.getconfigwithfallback('footkeysconfig.py')

def startkeys(args):
    pid = config.getpid(args.pidfile)
    if config.processexists(pid, procname=args.procname):
        log.error("Exiting: %s already running. pid=%d pidfile=%s", args.procname, pid, args.pidfile)
        sys.exit(1)
    config.writepid(args.pidfile)
    fk = FootKeys(displayname=args.display, configfilename=args.configfile)
    fk.loadconfig()
    try:
        fk.xwatch.flush()
        xevent.run([fk.xwatch, fk.sigwatch], logfilename='footkeyserrors.log')
    finally:
        fk.uninstall()

def sendreloadsignal(args):
    pid = config.getpid(args.pidfile)
    try:
        os.kill(pid, signal.SIGUSR1)
    except (TypeError, ProcessLookupError):
        log.error("Footkeys process %s does not exist..", pid)
        retcode = 1
    except PermissionError:
        # Exists, but we can't write to the process.
        log.error("Footkeys process %d exists, but permission to signal it is denied..", pid)
        retcode = 2
    else:
        log.info("Reload signal sent to process %d", pid)
        retcode = 0
    sys.exit(retcode)

def parseargs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--configfile', default=getconfigfilename(), help='Full path to configuration file. default: %(default)s')
    parser.add_argument('--pidfile', default=config.getpidfilename(parser.prog), help='Full path to pid file. default: %(default)s')
    parser.add_argument('--display', help='X display name. eg, :0.1. default: %(default)s')
    logger.addargs(parser)
    commands = nestedarg.NestedSubparser(parser.add_subparsers())
    with commands('start', aliases=['s'], help='run a footkeys instance.') as c:
        c.set_defaults(command=startkeys, procname=parser.prog)
    with commands('reload', aliases=['r'], help='reload configuration') as c:
        c.set_defaults(command=sendreloadsignal)
    args = parser.parse_args()
    return args

def main():
    args = parseargs()
    logger.startlogging(modulenames=args.logmodules, levelname=args.loglevel, outfilename=args.logfile)
    args.command(args)
