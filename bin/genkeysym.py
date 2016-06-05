#! /usr/bin/env python3

import re
import sys

def keymappairs(filename):
    p = re.compile(r'#define XK_([a-zA-Z_0-9]+)\s+0x([0-9a-f]+)\s*')
    with open(filename) as f:
        for x in f:
            m = p.match(x)
            if m:
                yield m.group(1), int(m.group(2), 16)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--keysymdef', default='/usr/include/X11/keysymdef.h', help='X keysymdef header file. Default: %(default)s')
    parser.add_argument('out', nargs='?', default='-', help='Output file. Default: stdout')
    args = parser.parse_args()
    if args.out == '-':
        p = print
    else:
        import functools
        p = functools.partial(print, file=open(args.out, 'w'))
    p('# Autogenerated by {}. DO NOT EDIT.'.format(sys.argv[0]))
    keypairs = [('NoSymbol', 0)] + [(key, num) for key, num in keymappairs(args.keysymdef)]
    # Output the keysym ids dict.
    p('keysymids = dict([')
    for k, v in keypairs:
        p("        ('{}', 0x{:08x}),".format(k, v))
    p('        ])')
    # Output the keysym names dict.
    p('keysymnames = dict([')
    for k, v in keypairs:
        p("        (0x{:08x}, '{}'),".format(v, k))
    p('        ])')