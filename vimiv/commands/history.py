# vim: ft=python fileencoding=utf-8 sw=4 et sts=4
"""Functions to read and write command history."""

import collections
import os

from vimiv.utils import xdg


def read():
    """Read command history from file."""
    filename = xdg.join_vimiv_data("history")
    # Create empty history file
    if not os.path.isfile(filename):
        with open(filename, "w") as f:
            f.write("")
        return []
    # Read from file
    history = []
    with open(filename) as f:
        for line in f.readlines():
            history.append(line.rstrip("\n"))
    return history


def write(commands):
    """Write command history to file.

    Args:
        commands: List of commands.
    """
    filename = xdg.join_vimiv_data("history")
    with open(filename, "w") as f:
        for command in commands:
            f.write(command + "\n")


class History(collections.UserList):
    """Store and interact with command line history.

    Implemented as a list which stores the commands in the history.

    Attributes:
        _index: Index of the currently %% command.
        _max_items: Integer defining the maximum amount of items to store.
        _temporary_element_stored: Bool telling if a temporary text stored in
            history during cycle.
    """

    def __init__(self, commands, max_items=100):
        super().__init__()
        self.extend(commands)
        self._index = 0
        self._max_items = max_items
        self._temporary_element_stored = False

    def update(self, command):
        """Update history with a new command.

        Args:
            command: New command to be inserted.
        """
        self.reset()
        if command in self:
            self.remove(command)
        self.insert(command)

    def reset(self):
        """Reset history when command was run."""
        self._index = 0
        if self._temporary_element_stored:
            self.pop(i=0)
            self._temporary_element_stored = False

    def insert(self, command):
        """Insert a command into the history.

        Overridden parent function as the index is always 0 and the list should
        never exceed a maximum length.

        Args:
            command: New command to be inserted.
        """
        super().insert(0, command)
        self.data = self.data[:self._max_items]

    def cycle(self, direction, text):
        """Cycle through command history.

        Called from the command line by the command-history command.

        Args:
            direction: One of "next", "prev".
            text: Current text in the command line.
        Return:
            The received command string to set in the command line.
        """
        if not self:
            return ""
        if not self._temporary_element_stored:
            self.insert(text)
            self._temporary_element_stored = True
        if direction == "next":
            self._index = (self._index + 1) % len(self)
        else:
            self._index = (self._index - 1) % len(self)
        return self[self._index]