"""
App running module for footwm.

Copyright (c) 2016 Akce
"""
# Python standard modules.
import argparse
import os
import socket
import stat
import sys

# Local modules.
from . import jsonrpc
from . import log as loghelp
from . import nestedarg
from . import runner
from . import selectloop

log = loghelp.make(name=__name__)

class SelectRunner:

    def __init__(self):
        self._loop = selectloop.EventLoop()
        self._run = runner.Runner()

    def addclient(self, conn):
        """ Server: add a new client connection to the selectloop. """
        jsonreceiver = jsonrpc.LocalObject(self._run)
        self._loop.add_client(selectloop.StreamRemote(sock=conn, receiver=jsonreceiver))

    def go(self, server):
        # with timeout=0, connects a disconnected client immediately.
        self._loop.add_client(server, timeout=0)
        self._loop.serve_forever()

def daemonstart(args):
    """ Start a footrun daemon instance. """
    # Since we're using Unix sockets, we need to remove stale socket files or
    # we'll get Address in use errors when we try to connect.
    try:
        st = os.stat(args.sockname)
    except (FileNotFoundError, OSError) as e:
        pass
    else:
        # Only remove the file if it is a unix domain socket file.
        if stat.S_ISSOCK(st.st_mode):
            os.unlink(args.sockname)
        else:
            # File exists but is not a socket, don't remove and halt execution!
            print('File {} exists and is not a unix socket. Remove or specify alternate filename.'.format(args.sockname), file=sys.stderr)
            sys.exit(1)
    run = SelectRunner()
    server = selectloop.StreamServer(address=args.sockname, family=socket.AF_UNIX, newconn=run.addclient)
    run.go(server)

def run(address, cmdline):
    remote = selectloop.StreamClient(address=address, family=socket.AF_UNIX)
    remote.connect()
    runner = jsonrpc.RemoteObject(['run'], postfunc=remote.post)
    runner.run(cmdline=cmdline)

def clirun(args):
    run(address=args.sockname, cmdline=' '.join('"{}"'.format(x) for x in args.args))

def makeargparser():
    parser = argparse.ArgumentParser()

    connparser = argparse.ArgumentParser(add_help=False)
    connparser.add_argument('--sockname', default='footrun.sock', help='unix socket filename. default: %(default)s')

    commands = nestedarg.NestedSubparser(parser.add_subparsers())
    with commands('daemon', aliases=['d'], parents=[connparser], help='app running daemon commands') as c:
        d = nestedarg.NestedSubparser(c.add_subparsers())
        with d('start', help='start a footrun daemon') as d1:
            d1.set_defaults(command=daemonstart)
    with commands('run', aliases=['e', 'r'], parents=[connparser], help='run (execute) a command') as c:
        c.set_defaults(command=clirun)
        # TODO specify command output logging options.
        c.add_argument('args', nargs='+', help='command line arguments of command')
    return parser

def main():
    parser = makeargparser()
    args = parser.parse_args()
    args.command(args)