# Python standard modules.
import curses

# Local modules.
from . import common
from .. import log as logmodule
from . import util

log = logmodule.make(name=__name__)

class Model:
    """ The data that the listbox will display. """

    def __init__(self, showindex=True, showheader=True, rows=None, columns=None):
        # Store the original columns and rows before any filtering.
        self._rows = rows or []
        self._columns = columns or []
        self.showindex = showindex
        # Can only show the column header if there are column names.
        self.showheader = showheader and self.columns

    @property
    def columns(self):
        cols = ([' # '] if self.showindex else []) + self._columns
        return cols

    @property
    def rows(self):
        if self.showindex:
            ret = [["{:2d}".format(i)] + row for i, row in enumerate(self._rows, 1)]
        else:
            ret = self._rows
        return ret

class ListBox(common.PanelWindowMixin):

    def __init__(self, parent, geom=None, model=None):
        self._reset()
        super().__init__(parent, geom)
        self._update_scroll()
        self.model = model

    def _update_scroll(self):
        # Ensure _scroll is at least 1, no point having a zero scroll value.
        self._scroll = max(int(self._geom.h / 2), 1)

    def _reset(self):
        self._viewport_index = 0
        self._selected_index = 0

    def resize(self, geom):
        super().resize(geom)
        self._update_scroll()
        self._update_viewport()

    def draw(self):
        ## Setup common colours.
        columncolour = curses.color_pair(0)
        headercolour = columncolour
        self._win.erase()
        self._win.box()
        geom = self._geom
        borders = 2
        headerlines = 2 if self.model.showheader else 0
        maxrows = geom.h - borders - headerlines
        # Get our slice of display items, then display them.
        sl = self.model.rows[self._viewport_index:self._viewport_index + maxrows]
        ## Calculate the max width of each row.
        # Note that the column headers are included in this calculation!
        rowmaxes = []
        columns = self.model.columns if self.model.showheader else []
        for i, row in enumerate([columns] + sl, 1):
            for j, col in enumerate(row):
                length = len(col)
                try:
                    oldmax = rowmaxes[j]
                except IndexError:
                    rowmaxes.append(length)
                else:
                    rowmaxes[j] = max(rowmaxes[j], length)

        ## Draw the verticle column divider lines.
        xbase = 2
        ybase = 0
        xpos = xbase
        # Don't draw the last column.
        for rm in rowmaxes[:-1]:
            xpos += rm + 1
            self._win.addch(ybase, xpos, curses.ACS_TTEE)
            self._win.vline(ybase + 1, xpos, curses.ACS_VLINE, geom.h - ybase - 1)
            self._win.addch(geom.h - 1, xpos, curses.ACS_BTEE)
            xpos += 2

        ## Draw column headers.
        if self.model.showheader:
            ybase += 1
            xpos = xbase
            for rm, columnname in zip(rowmaxes, columns):
                self._win.addstr(ybase, xpos, columnname, headercolour)
                xpos += rm + 3
            ## Draw column header divider line.
            ybase += 1
            self._win.addch(ybase, geom.x, curses.ACS_LTEE)
            xpos = 1
            self._win.hline(ybase, xpos, curses.ACS_HLINE, geom.w - borders)
            xpos = xbase
            for rm in rowmaxes[:-1]:
                xpos += rm + 1
                self._win.addch(ybase, xpos, curses.ACS_PLUS)
                xpos += 2
            self._win.addch(ybase, geom.w - 1, curses.ACS_RTEE)

        ## Draw row contents.
        #log.debug('listbox.draw len(slice)=%s h=%s viewport_index=%s', len(sl), self.h, self._viewport_index)
        ybase += 1
        for i, row in enumerate(sl):
            if i == (self._selected_index - self._viewport_index):
                textcolour = curses.color_pair(0) | curses.A_BOLD
            else:
                textcolour = curses.color_pair(0)
            xpos = xbase
            for rowmax, col in zip(rowmaxes, row):
                text = util.clip_end(col, geom.w - 1)
                self._win.addstr(i + ybase, xpos, text, textcolour)
                xpos += rowmax + 3
        super().draw()

    def down(self):
        self._down(1)

    def pagedown(self):
        self._down(self._scroll)

    def _down(self, count):
        self._selected_index += count
        if self._selected_index >= len(self.model.rows):
            self._selected_index = len(self.model.rows) - 1
        self._update_viewport()

    def up(self):
        self._up(1)

    def pageup(self):
        self._up(self._scroll)

    def _up(self, count):
        self._selected_index = max(self._selected_index - count, 0)
        self._update_viewport()

    def _update_viewport(self):
        """ Calculates _viewport_index position w/respect to screen LINES. Scroll the viewport if needed. """
        # Is the selected item visible on screen?
        geom = self._geom
        log.debug('update_viewport old listbox=%s _selected_index=%s _viewport_index=%s _scroll=%s', geom, self._selected_index, self._viewport_index, self._scroll)
        # offset makes sure that the selected item is visible on screen.
        # This calc only works because self._scroll is h/2. Doing the subtraction accounts for case where self.h == 1.
        # Could probably do this nicer but it works for now..
        offset = geom.h - self._scroll
        if self._selected_index < self._viewport_index:
            # Selected item is above viewport, try and centre the item on screen.
            self._viewport_index = max(self._selected_index - offset, 0)
        elif self._selected_index >= (self._viewport_index + geom.h):
            # Selected item is below viewport+pageheight, try and centre the item on screen.
            self._viewport_index = self._selected_index - offset
        log.debug('update_viewport new listbox=%s _selected_index=%s _viewport_index=%s _scroll=%s', geom, self._selected_index, self._viewport_index, self._scroll)

    @property
    def selected(self):
        """ Return the current selected index. """
        return self._selected_index

    @selected.setter
    def selected(self, newindex):
        try:
            item = self.model.rows[newindex]
        except IndexError:
            log.error('ListBox.selected failed. index=%d out of range=%d!', newindex, len(self.model.rows))
        else:
            log.debug('newindex=%s oldindex=%s newlabel=%s', newindex, self._selected_index, item)
            self._selected_index = newindex
            self._update_viewport()
