"""A generic subcommand handler. 
This does nothing other than dispatch to subcommands or output path info.
"""

# This is based on the `jupyter` command from the `jupyter_core` library.
# Original work copyright (c) Jupyter Development Team.
# Modifications copyright (c) Shani Armon
# Distributed under the terms of the Modified BSD License.

from __future__ import print_function

import argparse
import errno
import json
import os
import sys
import sysconfig
from subprocess import Popen

from shutil import which


class CommandMissing(Exception):
    pass


class CommandParser(argparse.ArgumentParser):
    def __init__(self, command_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_name = command_name

    @property
    def epilog(self):
        """Add subcommands to epilog on request
        Avoids searching PATH for subcommands unless help output is requested.
        """
        return "Available subcommands: %s" % " ".join(
            list_subcommands(self.command_name)
        )

    @epilog.setter
    def epilog(self, x):
        """Ignore epilog set in Parser.__init__"""
        pass


def command_parser(name, description):
    parser = CommandParser(command_name=name, description=description)
    group = parser.add_mutually_exclusive_group(required=True)
    # don't use argparse's version action because it prints to stderr on py2
    group.add_argument(
        "--version",
        action="store_true",
        help=f"show the {name} command's version and exit",
    )
    group.add_argument(
        "subcommand", type=str, nargs="?", help="the subcommand to launch"
    )

    return parser


def list_subcommands(command_name):
    """List all subcommands
    searches PATH for `<command>-name`
    Returns a list of <command>'s subcommand names, without the `<command>-` prefix.
    Nested children (e.g. <command>-sub-subsub) are not included.
    """
    subcommand_tuples = set()
    # construct a set of `('foo', 'bar') from `<command>-foo-bar`
    for d in _path_with_self():
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if name.startswith(f"{command_name}-"):
                if sys.platform.startswith("win"):
                    # remove file-extension on Windows
                    name = os.path.splitext(name)[0]
                subcommand_tuples.add(tuple(name.split("-")[1:]))
    # build a set of subcommand strings, excluding subcommands whose parents are defined
    subcommands = set()
    # Only include `<command>-foo-bar` if `<command>-foo` is not already present
    for sub_tup in subcommand_tuples:
        if not any(sub_tup[:i] in subcommand_tuples for i in range(1, len(sub_tup))):
            subcommands.add("-".join(sub_tup))
    return sorted(subcommands)


def _execvp(cmd, argv):
    """execvp, except on Windows where it uses Popen
    Python provides execvp on Windows, but its behavior is problematic (Python bug#9148).
    """
    if sys.platform.startswith("win"):
        # PATH is ignored when shell=False,
        # so rely on shutil.which
        try:
            from shutil import which
        except ImportError:
            from .utils.shutil_which import which
        cmd_path = which(cmd)
        if cmd_path is None:
            raise OSError("%r not found" % cmd, errno.ENOENT)
        p = Popen([cmd_path] + argv[1:])
        # Don't raise KeyboardInterrupt in the parent process.
        # Set this after spawning, to avoid subprocess inheriting handler.
        import signal

        signal.signal(signal.SIGINT, signal.SIG_IGN)
        p.wait()
        sys.exit(p.returncode)
    else:
        os.execvp(cmd, argv)


def _command_abspath(name, subcommand):
    """This method get the abspath of a specified <name>-<subcommand> with no 
    changes on ENV.
    """
    # get env PATH with self
    search_path = os.pathsep.join(_path_with_self())
    # get the abs path for the <name>-<subcommand>
    subcommand_name = f"{name}-{subcommand}"
    abs_path = which(subcommand_name, path=search_path, mode=os.F_OK)
    if abs_path is None:
        raise CommandMissing(
            f"{name.capitalize()} command `{subcommand_name}` not found."
        )

    if not os.access(abs_path, os.X_OK):
        raise CommandMissing(
            f"{name.capitalize()} command `{subcommand_name}` is not executable."
        )

    return abs_path


def _path_with_self():
    """Put `<name>`'s dir at the front of PATH
    Ensures that /path/to/<name> subcommand
    will do /path/to/<name>-subcommand
    even if /other/<name>-subcommand is ahead of it on PATH
    """
    path_list = (os.environ.get("PATH") or os.defpath).split(os.pathsep)

    # Insert the "scripts" directory for this Python installation
    # This allows the "<name>" command to be relocated, while still
    # finding subcommands that have been installed in the default
    # location.
    # We put the scripts directory at the *end* of PATH, so that
    # if the user explicitly overrides a subcommand, that override
    # still takes effect.
    try:
        bindir = sysconfig.get_path("scripts")
    except KeyError:
        # The Python environment does not specify a "scripts" location
        pass
    else:
        path_list.append(bindir)

    scripts = [sys.argv[0]]
    if os.path.islink(scripts[0]):
        # include realpath, if `<name>` is a symlink
        scripts.append(os.path.realpath(scripts[0]))

    for script in scripts:
        bindir = os.path.dirname(script)
        if os.path.isdir(bindir) and os.access(
            script, os.X_OK
        ):  # only if it's a script
            # ensure executable's dir is on PATH
            # avoids missing subcommands when <name> is run via absolute path
            path_list.insert(0, bindir)
    return path_list


def subcommand(name=None, description=None, version=None):
    if name is None:
        name = os.path.basename(sys.argv[0])

    if name == "generic_subcommand":
        sys.exit("This executable is meant to be symlinked and not directly executed")

    if description is None:
        description = f"Subcommand parser for '{name}' command"

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Don't parse if a subcommand is given
        # Avoids argparse gobbling up args passed to subcommand, such as `-h`.
        subcommand = sys.argv[1]
    else:
        parser = command_parser(name, description)
        args, opts = parser.parse_known_args()
        subcommand = args.subcommand
        if args.version:
            print(f"{name:<17}:", version)
            return

    if not subcommand:
        parser.print_usage(file=sys.stderr)
        sys.exit("subcommand is required")

    try:
        command = _command_abspath(name, subcommand)
    except CommandMissing as e:
        sys.exit(e)

    try:
        _execvp(command, sys.argv[1:])
    except OSError as e:
        sys.exit(
            f"Error executing {name.capitalize()} command {subcommand}: {e}. errno={e.errno}"
        )


if __name__ == "__main__":
    subcommand()
