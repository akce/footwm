""" Common config utilities. """

# Python standard modules.
import os
import subprocess

def getuserconfig(basename):
    """ User config by default is in ~/.foot/ """
    return os.path.join(os.environ['HOME'], '.foot', basename)

def getconfigwithfallback(basename):
    """ Returns a config file name that exists.
    ie, Return the default config from the source directory if the
    config file doesn't exist in the users home directory.
    """
    homefile = getuserconfig(basename)
    # Test if there's config file in the home directory.
    if os.path.isfile(homefile):
        cf = homefile
    else:
        # Fallback to the sample config footkeysconfig.py in the source directory.
        cf = os.path.join(os.path.split(os.path.realpath(__file__))[0], basename)
    return cf

def loadconfig(filename, globals_=None, locals_=None):
    """ Loads a config file consisting of python code.
    Using this probably has security implications.
    """
    gs = globals() if globals_ is None else globals_
    ls = locals() if locals_ is None else locals_
    with open(filename) as f:
        codeobj = compile(f.read(), filename, 'exec')
        exec(codeobj, gs, ls)

def getpidfilename(basename):
    return os.path.join(os.environ['HOME'], '.foot', '{}.pid'.format(basename))

def getpid(filename):
    try:
        with open(filename) as f:
            pid = int(f.read())
    except (FileNotFoundError, ValueError):
        pid = None
    return pid

def writepid(filename, pid=None):
    pidstr = str(pid or os.getpid())
    with open(filename, 'w') as f:
        f.write(pidstr)

def processexists(pid, procname):
    """ True if pid exists and is the same as our process name. """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        exists = False
    except PermissionError:
        # Exists, but we can't write to the process.
        exists = True
    except TypeError:
        # pid is not a valid input. It's most likely a None.
        exists = False
    else:
        # PID exists, let's see if the process name is the same as ours.
        # Use ps as the most portable way of extracting the process name.
        # The ps args only prints the command for pid and suppresses the header line.
        # See 'man ps' for why.
        out = subprocess.check_output(['ps', '-o', 'args=', '-p', str(pid)])
        # The output will look like:
        # python3 /home/user/footwm/bin/footkeys start (python3.6)
        # The gymnastics below will extract the 'footkeys' portion.
        outproc = str(os.path.split(out.rstrip().split()[1])[1], 'utf8')
        exists = outproc == procname
    return exists
