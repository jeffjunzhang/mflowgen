#! /usr/bin/env python
#=========================================================================
# ninja_syntax_extra.py
#=========================================================================
#
# Author : Christopher Torng
# Date   : June 2, 2019
#

import os

from .utils import stamp, get_top_dir

#-------------------------------------------------------------------------
# Extra ninja helper functions
#-------------------------------------------------------------------------

# ninja_cpdir
#
# Copies a directory and handles stamping
#
# - w    : instance of ninja_syntax Writer
# - dst  : path to copied directory
# - src  : path to source directory
# - deps : list, additional dependencies for ninja build
#

def ninja_cpdir( w, dst, src, deps=None, parameterize=None ):

  if deps:
    assert type( deps ) == list, 'Expecting deps to be of type list'

  if parameterize:
    rule = 'cpdir-and-parameterize'
  else:
    rule = 'cpdir'

  target = dst + '/.stamp'

  w.build(
    outputs   = target,
    implicit  = [ src ] + deps,
    rule      = rule,
    variables = { 'dst'   : dst,
                  'src'   : src,
                  'stamp' : target },
  )

  return target

# ninja_symlink
#
# Symlinks src to dst while handling stamping
#
# - w    : instance of ninja_syntax Writer
# - dst  : path to linked file/directory
# - src  : path to source file/directory
# - deps : additional dependencies for ninja build
# - src_is_symlink : boolean, flag if source is a symlink (and has stamp)
#

def ninja_symlink( w, dst, src, deps=None, src_is_symlink=False ):

  if deps:
    assert type( deps ) == list, 'Expecting deps to be of type list'

  # Stamp files

  dst_dir   = os.path.dirname( dst )
  dst_base  = os.path.basename( dst )
  dst_stamp = stamp( dst )

  # Relative paths for symlinking after changing directories

  src_relative = os.path.relpath( src, dst_dir )
  dst_relative = dst_base
  dst_stamp_relative = os.path.basename( dst_stamp )

  # Depend on src stamp if src is also a symlink

  if src_is_symlink:
    src_dir   = os.path.dirname( src )
    src_base  = os.path.basename( src )
    src_stamp = stamp( src )
    inputs    = src_stamp
  else:
    inputs    = src

  # Ninja

  target = dst_stamp

  w.build(
    outputs   = target,
    implicit  = [ inputs ] + deps,
    rule      = 'symlink',
    variables = { 'dst_dir' : dst_dir,
                  'dst'     : dst_relative,
                  'src'     : src_relative,
                  'stamp'   : dst_stamp_relative },
  )

  return target

# ninja_execute
#
# Runs the execute rule
#
# - w       : instance of ninja_syntax Writer
# - outputs : outputs of the execute rule
# - rule    : name of the execute rule
# - command : string, command for the rule
# - deps    : additional dependencies for ninja build
#

def ninja_execute( w, outputs, rule, command, description='', deps=None, pool='' ):

  if deps:
    assert type( deps ) == list, 'Expecting deps to be of type list'

  rule_params = {
    'name'        : rule,
    'command'     : command,
    'description' : description,
    'pool'        : pool,
  }

  if not pool:
    del( rule_params['pool'] )

  if not description:
    del( rule_params['description'] )

  w.rule( **rule_params )

  w.newline()

  w.build(
    outputs  = outputs,
    implicit = deps,
    rule     = rule,
  )

  w.newline()

  return outputs

# ninja_stamp
#
# Stamps the given file with a '.stamp.' prefix
#
# - w       : instance of ninja_syntax Writer
# - f       : file to stamp
# - deps    : additional dependencies for ninja build
#

def ninja_stamp( w, f, deps=None ):

  if deps:
    assert type( deps ) == list, 'Expecting deps to be of type list'

  f_stamp = stamp( f )

  w.build(
    outputs   = f_stamp,
    implicit  = [ f ] + deps,
    rule      = 'stamp',
    variables = { 'stamp' : f_stamp },
  )

  w.newline()

  return f_stamp

# ninja_alias
#
# Create an alias for the given dependencies
#
# - w     : instance of ninja_syntax Writer
# - alias : alias name(s)
# - deps  : dependencies
#

def ninja_alias( w, alias, deps ):

  if deps:
    assert type( deps ) == list, 'Expecting deps to be of type list'

  w.build(
    outputs  = alias,
    implicit = deps,
    rule     = 'phony',
  )

  w.newline()

  return alias

# ninja_common_rules
#
# Write out the common ninja rules
#
# - w : instance of ninja_syntax Writer
#

def ninja_common_rules( w ):

  # cpdir

  w.rule(
    name        = 'cpdir',
    description = 'cpdir: Copying $src to $dst',
    command     = 'rm -rf ./$dst && ' +
                  'cp -aL $src $dst && ' +
                  'touch $stamp',
  )
  w.newline()

  # cpdir-and-parameterize
  #
  # Copies a parameterized YAML into the new build directory

  w.rule(
    name        = 'cpdir-and-parameterize',
    description = 'cpdir-and-parameterize: Copying $src to $dst',
    command     = 'rm -rf ./$dst && ' +
                  'cp -aL $src $dst && ' +
                  'cp .mflow/$dst/configure.yaml $dst && ' +
                  'touch $stamp',
  )
  w.newline()

  # symlink

  w.rule(
    name        = 'symlink',
    description = 'symlink: Symlinking $src to $dst',
    command     = 'cd $dst_dir && ln -sf $src $dst && touch $stamp',
  )
  w.newline()

  # stamp

  w.rule(
    name        = 'stamp',
    description = 'stamp: Stamping at $stamp',
    command     = 'touch $stamp',
  )
  w.newline()

# ninja_clean
#
# Write out ninja rules for cleaning
#
# - w : instance of ninja_syntax Writer
#

def ninja_clean( w, command ):

  w.rule(
    name        = 'clean',
    description = 'clean: Clean all build directories',
    command     = command,
  )
  w.newline()

  w.build(
    outputs = 'clean',
    rule    = 'clean',
  )
  w.newline()


# ninja_runtimes
#
# Write out ninja rules for calculating runtimes from timestamps
#
# - w : instance of ninja_syntax Writer
#

def ninja_runtimes( w ):

  w.rule(
    name        = 'runtimes',
    description = 'runtimes: Listing runtimes for each step',
    command     = 'python ' + get_top_dir() + '/utils/runtimes.py',
  )
  w.newline()

  w.build(
    outputs = 'runtimes',
    rule    = 'runtimes',
  )
  w.newline()

# ninja_list
#
# Write out ninja rule to list all steps
#
# - w             : instance of ninja_syntax Writer
# - steps         : list of steps
# - debug_targets : list of debug targets
#

def ninja_list( w, steps, debug_targets ):

  steps_str = \
    [ '"{: >2} : {}"'.format(i,x) for i, x in enumerate( steps ) ]

  special = [
    '"list     -- List all targets"',
    '"runtimes -- Print runtimes for each step"',
    '"graph    -- Generate a PDF of the step dependency graph"',
    '"clean    -- Remove all build directories"',
  ]

  commands = [
    'echo',
    'echo Special Targets\: && echo && ' + \
      'printf " - %s\\n" ' + ' '.join( special ),
    'echo',
    'echo Targets\: && echo && ' + \
      'printf " - %s\\n" ' + ' '.join( steps_str ),
    'echo',
    'echo Debug Targets\: && echo && ' + \
      'printf " - %s\\n" ' + ' '.join( debug_targets ),
    'echo',
  ]

  command = ' && '.join( commands )

  w.rule(
    name        = 'list',
    description = 'list: Listing all targets',
    command     = command,
  )
  w.newline()

  w.build(
    outputs = 'list',
    rule    = 'list',
  )
  w.newline()

# ninja_graph
#
# Write out ninja rule to generate a PDF of the user-defined graph
#
# - w : instance of ninja_syntax Writer
#

def ninja_graph( w ):

  command = 'dot -Tpdf .mflow/graph.dot > graph.pdf'

  w.rule(
    name        = 'graph',
    description = 'graph: Generating a PDF of the user-defined graph',
    command     = command,
  )
  w.newline()

  w.build(
    outputs = 'graph',
    rule    = 'graph',
  )
  w.newline()

# ninja_graph_detailed
#
# Write out ninja rule to generate a PDF of the build system's dependency
# graph.
#
# - w          : instance of ninja_syntax Writer
# - build_dirs : list of build directories
#
# The build directories are used to create subgraphs in the default ninja
# build graph.. otherwise the graph is too messy to see anything in.
#

def ninja_graph_detailed( w, build_dirs ):

  build_dirs_commas = ','.join( build_dirs )

  python_graph_cmd = ' '.join([
    'python',
    get_top_dir() + '/utils/graph.py',
    '-t ' + build_dirs_commas,
    '-g .graph.dot',
    '-o .graph.subgraph.dot',
  ])

  command = ' && '.join([
    'ninja -t graph > .graph.dot',
    python_graph_cmd,
    'dot -Tps2 .graph.subgraph.dot > .graph.ps2',
    'ps2pdf .graph.ps2 graph.pdf',
  ])

  w.rule(
    name        = 'graph',
    description = 'graph: Generating the build graph',
    command     = command,
  )
  w.newline()

  w.build(
    outputs = 'graph',
    rule    = 'graph',
  )
  w.newline()

