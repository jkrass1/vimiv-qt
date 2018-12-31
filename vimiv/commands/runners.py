# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2018 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Classes and functions to run commands."""

import logging
import os
import re
import shlex
import subprocess

from PyQt5.QtCore import QRunnable, QObject, QThreadPool, pyqtSignal, pyqtSlot

from vimiv import app
from vimiv.commands import commands, cmdexc, aliases
from vimiv.gui import statusbar
from vimiv.modes import modehandler
from vimiv.utils import pathreceiver


def update_command(text, mode):
    """Update command with aliases and wildcards.

    Args:
        text: String passed as command.
        mode: Mode in which the command is supposed to run.
    """
    return expand_wildcards(alias(text, mode), mode)


def command(text, mode=None):
    """Run internal command when called.

    Splits the given text into count, name and arguments. Then runs the
    command corresponding to name with count and arguments. Emits the
    exited signal when done.

    Args:
        text: String passed as command.
        mode: Mode in which the command is supposed to run.
    """
    if mode is None:
        mode = modehandler.current()
    count, cmdname, args = _parse(text)
    try:
        cmd = commands.get(cmdname, mode)
        cmd(args, count=count)
        statusbar.update()
        logging.debug("Ran '%s' succesfully", text)
    except cmdexc.CommandNotFound as e:
        logging.error(str(e))
    except (cmdexc.ArgumentError, cmdexc.CommandError) as e:
        logging.error("%s: %s", cmdname, str(e))
    except cmdexc.CommandWarning as w:
        logging.warning("%s: %s", cmdname, str(w))


def _parse(text):
    """Parse given command text into count, name and arguments.

    Args:
        text: String passed as command.
    Return:
        count: Digits prepending the command to interpret as count.
        name: Name of the command passed.
        args: Arguments passed.
    """
    text = text.strip()
    count = ""
    split = shlex.split(text)
    cmdname = split[0]
    # Receive prepended digits as count
    while cmdname and cmdname[0].isdigit():
        count += cmdname[0]
        cmdname = cmdname[1:]
    args = split[1:]
    return count, cmdname, args


def expand_wildcards(text, mode):
    """Expand % and * to the corresponding path and pathlist.

    Args:
        text: The command in which the wildcards are expanded.
        mode: Mode the command is run in to get correct path(-list).
    """
    # Check first as the re substitutions are rather expensive
    if "%" in text:
        current = pathreceiver.current(mode)
        text = re.sub(r'(?<!\\)%', current, text)
    if "*" in text:
        pathlist = " ".join(pathreceiver.pathlist())
        text = re.sub(r'(?<!\\)\*', pathlist, text)
    return text


class ExternalRunner(QObject):
    """Runner for external commands.

    Signals:
        pipe_output_received: Emitted when :!command | completes.
            arg1: The shell command that was executed.
            arg2: stdout of the shell command.
    """

    _pool = QThreadPool.globalInstance()
    pipe_output_received = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.pipe_output_received.connect(self._on_pipe_output_received)

    def __call__(self, text):
        """Run external command using ShellCommandRunnable.

        Args:
            text: Text parsed as command to run.
        """
        runnable = ShellCommandRunnable(text, self)
        self._pool.start(runnable)

    @pyqtSlot(str, str)
    def _on_pipe_output_received(self, cmd, stdout):
        """Open paths from stdout.

        Args:
            cmd: Executed shell command.
            stdout: String form of stdout of the exited shell command.
        """
        paths = [path for path in stdout.split("\n") if os.path.exists(path)]
        if paths and app.open_paths(paths):
            statusbar.update()
            logging.debug("Opened paths from pipe '%s'", cmd)
        else:
            logging.warning("%s: No paths from pipe", cmd)


external = ExternalRunner()


class ShellCommandRunnable(QRunnable):
    """Run shell command in an extra thread.

    Captures stdout and stderr. Logging is called according to the returncode
    of the command.

    Attributes:
        _text: Text parsed as command to run.
        _runner: ExternalRunner that started this runnable.
        _pipe: Whether to check stdout for paths to open.
    """

    def __init__(self, text, runner):
        super().__init__()
        self._text = text.rstrip("|").strip()
        self._runner = runner
        self._pipe = bool(text.endswith("|"))

    def run(self):
        """Run shell command on QThreadPool.start(self)."""
        try:
            pargs = subprocess.run(self._text, shell=True, check=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            if self._pipe:
                self._runner.pipe_output_received.emit(self._text,
                                                       pargs.stdout.decode())
            else:
                logging.debug("Ran '!%s' succesfully", self._text)
        except subprocess.CalledProcessError as e:
            message = e.stderr.decode().split("\n")[0]
            logging.error("%d  %s", e.returncode, message)


def alias(text, mode):
    """Replace alias with the actual command.

    Return:
        The replaced text if text was an alias else text.
    """
    cmd = text.split()[0]
    if cmd in aliases.get(mode):
        return text.replace(cmd, aliases.get(mode)[cmd])
    return text
