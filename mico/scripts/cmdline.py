#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# vim:fenc=utf-8:

import os
import sys
import cmd
import shlex
import random
import pkgutil
import inspect

import mico
import mico.fifo
import mico.util
import mico.hook
import mico.output

from mico.template import Template

class MicoCmdline(cmd.Cmd):
    """The command line console which will be invoked from mico script."""

    template_path = [
            "templates",
            "data",
            "content",
            "files",
            "sources"
    ]
    ruler     = '-'
    prompt    = mico.output.prompt_usr
    intro     = mico.output.prompt_msg + random.choice(mico.output.intros)

    def complete(self, text, state):
        "Return a list of completion options for console."

        options =  [i for i in map(lambda x:x[3:], filter(lambda x:x.startswith("do_"), dir(self) )) if i.startswith(text) if i != "EOF" ]
        options += [i for j in map(pkgutil.iter_modules, mico.config_path) for _,i,_ in j]

        if state < len(options):
            return options[state]
        else:
            return None

    def emptyline(self):
        pass

    def do_set(self, args):
        "Set an environment variable, in teh form variable=value"
        if "=" in args:
            args = args.split("=")
            val  = " ".join(args[1:])

            if val == "True" or val == "true":
                val = True
            elif val == "False" or val == "false":
                val = False
            else:
                val = "'%s'" % val

            try:
                eval("env.__setitem__('%s',%s)" % ( args[0], val ))
            except Exception, e:
                mico.output.error("invalid evaluation: %s" % e)
        else:
            mico.output.error("invalid syntax, required var=value")


    def do_host(self, host=[]):
        "Set hosts where command must run."

        if host:
            if "," in host:
                host = host.split(",")
            else:
                host = [ host ]

            env.hosts = host

    def do_env(self, args):
        "Print current environment."
        if args:
            if " " in args:
                args = split(" ")
            else:
                args = [ args ]

        for key in env:
            if not args or key in args:
                mico.output.puts("%-20s = %s" % ( key, env[key] ) )


    def do_EOF(self, *args):
        "Exits the shell, also works by pressing C-D."
        return True
    do_exit = do_EOF

    def do_peanut(self, *args):
        print mico.output.monkey

    def do_help(self, arg):
        'List available commands with "help" or detailed help with "help cmd"'
        def _load_all_modules_from_dir(dirname):
            for importer, package_name, _ in pkgutil.walk_packages([dirname]):
                if package_name == "setup":
                    continue
                full_package_name = '%s.%s' % (dirname, package_name)
                if full_package_name not in sys.modules:
                    module = importer.find_module(package_name).load_module(full_package_name)
                    yield package_name, module

        names = self.get_names()
        cmds_doc = []
        cmds_undoc = []
        help = {}
        for name in names:
            if name[:5] == 'help_':
                help[name[5:]]=1
        names.sort()
        # There can be duplicates if routines overridden
        prevname = ''
        for name in names:
            if name[:3] == 'do_':
                if name == prevname:
                    continue
                prevname = name
                cmd=name[3:]
                if cmd in help:
                    cmds_doc.append(cmd)
                    del help[cmd]
                elif getattr(self, name).__doc__:
                    cmds_doc.append(cmd)
                else:
                    cmds_undoc.append(cmd)


        if len(cmds_doc):
            if arg and arg in cmds_doc:
                # Show help for internal command
                try:
                    func = getattr(self, 'help_' + arg)
                except AttributeError:
                    try:
                        doc=getattr(self, 'do_' + arg).__doc__
                        if doc:
                            self.stdout.write("%s\n"%str(doc))
                            return
                    except AttributeError:
                        pass
                    self.stdout.write("%s\n"%str(self.nohelp % (arg,)))
                    return
                return func()
            else:
                print "[33;1minternals[0;0m"
                print "Internal commands for mico which are implemented in mico itself."
                print
                for cmd in cmds_doc:
                    print "%-15s%-s" % (cmd, getattr(self, "do_%s" % cmd).__doc__)
                print

        if len(mico.config_path):
            for path in mico.config_path:
                if path == ".":
                    continue
                try:
                    for pkgname, module in _load_all_modules_from_dir(path):
                        if not arg or arg == pkgname:
                            print "[33;1m%s[0;0m" % pkgname
                            if hasattr(module,"__doc__") and module.__doc__:
                                print "%s" % module.__doc__
                            print

                            for o in inspect.getmembers(module):
                                if inspect.isfunction(o[1]):
                                    if (module == inspect.getmodule(o[1])):
                                        if getattr(o[1],"__doc__"):
                                            print "[0;1m%s.%s[0;0m"% (pkgname, o[0],)
                                            print "    %s" % (o[1].__doc__)
                                            print
                except OSError:
                    pass


    def default(self, args):
        lexer = shlex.shlex(args)
        lexer.wordchars += "?*:/%&.-="
        lexer = tuple([ x for x in lexer ])

        mod, fun = lexer[0], ["main"]

        try:
            mod, fun = Template.load(mod, fun)
            if not mod.__name__.startswith("_mico_dm_"):
                mico.config_path.append(os.path.dirname(mod.__file__))
                for path in self.template_path:
                    mico.config_path.append(os.path.join(os.path.dirname(mod.__file__), path))
        except ImportError, e:
            mico.output.error("template '%s' not found: %s." % (mod,e,))
        except AttributeError, e:
            mico.output.error("function '%s' not found in template '%s': %s" % ( fun[0], mod, e, ))
        else:
            mico.execute(fun, False, *tuple(lexer[1:]))

def main():
    """Entrypoint for mico cmdline client."""
    import argparse

    cmdopt = argparse.ArgumentParser(
            description="mico: %s" % random.choice(mico.output.intros),
            epilog="©2012  Andrés J. Díaz <ajdiaz@connectical.com>")

    cmdopt.add_argument("-e", "--env", action="append",
                                      dest="env",
                                      help="set environment variable",
                                      type=str,
                                      default=[])
    cmdopt.add_argument("-H", "--host", action="append",
                                      dest="host",
                                      help="set host to target",
                                      type=str,
                                      default=[])
    cmdopt.add_argument("-R", "--region", action="store",
                                      dest="region",
                                      help="set EC2 region to work on",
                                      type=str,
                                      default="us-east-1")

    cmdopt.add_argument("-u", "--user", action="store",
                                      dest="user",
                                      help="set the user to use to connect to host",
                                      type=str,
                                      default=None)

    cmdopt.add_argument("-i", "--identity-file", action="store",
                                      dest="identity_file",
                                      help="set the key to use to connect to host",
                                      type=str,
                                      default=None)

    cmdopt.add_argument("-v", "--verbose", action="store_true",
                                      dest="verbose",
                                      help="be verbose",
                                      default=False)

    cmdopt.add_argument("-f", "--force", action="store_true",
                                      dest="force",
                                      help="force changes",
                                      default=False)

    cmdopt.add_argument("-np", "--no-parallel", action="store_false",
                                      dest="parallel",
                                      help="don't execute actions in parallel",
                                      default=True)

    cmdopt.add_argument("template",
                        nargs='*',
                        default=None,
                        help="The template:function to execute or an internal command")

    args = cmdopt.parse_args()

    try:
        cmdlne = MicoCmdline()
        cmdlne.preloop()

        for opt in args.env:
            cmdlne.do_set(opt)

        for host in args.host:
            cmdlne.do_host(host)

        if args.verbose:
            env.loglevel.add("debug")

        if args.user:
            env.user = args.user

        if args.identity_file:
            env.key_filename = args.identity_file

        env.force = args.force
        env.parallel = args.parallel
        env.ec2_region = args.region
        env.args = args

        if len(args.template) == 0:
            cmdlne.cmdloop()
        else:
            cmdlne.onecmd(" ".join(args.template))
    except Exception, e:
        if "debug" in env.loglevel:
            raise
        mico.output.error("unexpected error: %s: %s" % (e.__class__.__name__ ,e))

