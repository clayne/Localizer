#!/usr/bin/python3

# Copyright 2021 Yury Gribov
# 
# Use of this source code is governed by MIT license that can be
# found in the LICENSE.txt file.
#
# A simple script which locates functions in codebase which can
# be changed to statics (or moved to anon. namespace).

import argparse
import atexit
import json
import os
import os.path
import subprocess
import shutil
import sys
import tempfile

me = os.path.basename(__file__)

def warn(msg):
  """
  Print nicely-formatted warning message.
  """
  sys.stderr.write('%s: warning: %s\n' % (me, msg))

def error(msg):
  """
  Print nicely-formatted error message and exit.
  """
  sys.stderr.write('%s: error: %s\n' % (me, msg))
  sys.exit(1)

def warn_if(cond, msg):
  if cond:
    warn(msg)

def error_if(cond, msg):
  if cond:
    error(msg)

def run(cmd, **kwargs):
  """
  Simple wrapper for subprocess.
  """
  if 'fatal' in kwargs:
    fatal = kwargs['fatal']
    del kwargs['fatal']
  else:
    fatal = False
  if 'tee' in kwargs:
    tee = kwargs['tee']
    del kwargs['tee']
  else:
    tee = False
  if isinstance(cmd, str):
    cmd = cmd.split(' ')
#  print(cmd)
  p = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, **kwargs)
  out, err = p.communicate()
  out = out.decode()
  err = err.decode()
  if fatal and p.returncode != 0:
    error("'%s' failed:\n%s%s" % (' '.join(cmd), out, err))
  if tee:
    sys.stdout.write(out)
    sys.stderr.write(err)
  return p.returncode, out, err

class Symbol:
  def __init__(self, name):
    self.name = name
    self.defs = []
    self.uses = []

  def has_multiple_defs(self):
    return len(self.defs) > 1

  def is_imported(self):
    return len(self.uses) > 0

  def is_system_symbol(self):
    for origin in self.defs:
      if origin.startswith("/usr/") or origin.startswith("/lib/"):
        return True
    return False

class Symtab:
  def __init__(self):
    self.syms = {}
    self.imports = {}
    self.exports = {}

  def get_or_create(self, name):
    sym = self.syms.get(name)
    if sym is None:
      sym = self.syms[name] = Symbol(name)
    return sym

  def add_import(self, origin, name):
    sym = self.get_or_create(name)
    sym.uses.append(origin)
    self.imports.setdefault(name, []).append(origin)

  def add_export(self, origin, name):
    sym = self.get_or_create(name)
    sym.defs.append(origin)
    self.exports.setdefault(name, []).append(origin)

def analyze_reports(reports):
  # Collect global imports/exports
  symtab = Symtab()
  for report in reports:
    for s in report['exports']:
      symtab.add_export(s['file'], s['name'])
    for s in report['imports']:
      symtab.add_import(s['file'], s['name'])
    for s in report['global_exports']:
      # Here we assume that any symbol exported from shlib has potential outside uses
      # so can't be marked as static.
      # This is an over simplification because very often these exports are accidental.
      # But such cases should be checked by dedicated tool ShlibVisibilityChecker.
      symtab.add_import(s['file'], s['name'])

  # Warn about duplicated definitions
  for name, sym in sorted(symtab.syms.items()):
    if not sym.has_multiple_defs():
      continue
    if name[0] == '_':
      # Skip compiler-generated symbols
      continue
    if name in ('main'):
      # Skip duplicated symbols
      continue
    warn("symbol %s is defined in multiple files:\n  %s"
         % (name, '\n  '.join(sym.defs)))

  # Collect unimported symbols
  bad_syms = []
  for name, sym in sorted(symtab.syms.items()):
    if sym.is_system_symbol():
      # Skip system files
      continue
    if not sym.is_imported():
      bad_syms.append(sym)

  # Print report
  if bad_syms:
    print("Global symbols not imported by any file:")
    for sym in bad_syms:
      print("  %s (%s)" % (sym.name, sym.defs[0]))

def main():
  class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass
  parser = argparse.ArgumentParser(description="Find symbols which may be marked as static",
                                   formatter_class=Formatter,
                                   epilog="""\
Examples:
  $ python {0} make -j10
""".format(me))
  parser.add_argument('--keep', '-k',
                      help="Do not remove temp files",
                      dest='keep', action='store_true', default=False)
  parser.add_argument('--no-keep',
                      help="Inverse of --keep",
                      dest='keep', action='store_false')
  parser.add_argument('--tmp-dir',
                      help="Store temp files in directory")
  parser.add_argument('--verbose', '-v',
                      help="Print diagnostic info (can be specified more than once)",
                      action='count', default=0)
  parser.add_argument('cmd',
                      help="Program to run", metavar='ARG')
  parser.add_argument('args',
                      nargs=argparse.REMAINDER, default=[])

  args = parser.parse_args()

  tmp_dir = args.tmp_dir or tempfile.mkdtemp(prefix='find-locals-')
  shutil.rmtree(tmp_dir)
  os.makedirs(tmp_dir, exist_ok=True)
  if not args.keep:
    atexit.register(lambda: shutil.rmtree(tmp_dir))
  else:
    sys.stderr.write("%s: intermediate files will be stored in %s\n" % (me, tmp_dir))

  # Add linker wrappers to PATH
  bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'bin'))
  os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']

  # Pass settings via environment
  os.environ['LOCALIZER_DIR'] = tmp_dir
  os.environ['LOCALIZER_VERBOSE'] = str(args.verbose)

  rc, out, err = run([args.cmd] + args.args, fatal=True)
  sys.stdout.write(out)
  sys.stderr.write(err)

  if rc:
    sys.stderr.write("%s: not collecting data because build has errors\n" % me)
  else:
    reports = []
    for report_file in os.listdir(tmp_dir):
      with open(os.path.join(tmp_dir, report_file)) as f:
        reports.append(json.load(f))
    analyze_reports(reports)

  return rc

if __name__ == '__main__':
  sys.exit(main())