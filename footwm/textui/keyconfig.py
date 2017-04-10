import collections
import curses

keylabels = {
    10:			'ENTER',
    20:			'SPACE',
    27:			'ESC',
    curses.KEY_NPAGE:	'PAGEDOWN',
    curses.KEY_PPAGE:	'PAGEUP',
    curses.KEY_UP:	'UP',
    curses.KEY_DOWN:	'DOWN',
    curses.KEY_LEFT:	'LEFT',
    curses.KEY_RIGHT:	'RIGHT',
    curses.KEY_HOME:	'HOME',
    curses.KEY_END:	'END',
    }

keycodes = {v: k for k, v in keylabels.items()}

class Key:

    def __init__(self, key, label, code, action):
        self.key = key
        self.label = label
        self.code = code
        self.action = action

class KeyBuilder:

    def __init__(self, keyapp):
        self._keyapp = keyapp
        self._keymaps = collections.defaultdict(collections.OrderedDict)

    def addkey(self, key, action, label='', keymapname='root'):
        """ Adds a key/action pair to the named keymap. """
        try:
            code = keycodes[key]
        except KeyError:
            code = ord(key)
        self._keymaps[keymapname][code] = Key(key=key, label=label, code=code, action=action)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # No exception occurred, install the keymap.
            self._keyapp._installkeymap(self._keymaps)
