#!/usr/bin/python3
# encoding: utf-8

# --                                                            ; {{{1
#
# File        : common.py
# Maintainer  : Felix C. Stegerman <flx@obfusk.net>
# Date        : 2020-04-06
#
# Copyright   : Copyright (C) 2020  Felix C. Stegerman
# Version     : v0.0.1
# License     : AGPLv3+
#
# --                                                            ; }}}1

# NB: only works single-threaded!

import os, time

from flask import jsonify, redirect, url_for

POLL = 1000

class Oops(RuntimeError):
  def msg(self): return self.args[0]
class InProgress(Oops):
  def __init__(self): super().__init__("in progress")
class InvalidAction(Oops): pass
class InvalidParam(Oops):
  def msg(self): return "invalid parameter: " + self.args[0]

# global state
games = {}

def current_game(game):
  return games[game]

def restart_game(game):
  del games[game]

def update_game(game, new):
  cur = current_game(game)
  cur.update(new, tick = max(cur["tick"] + 1, int(time.time())))

def valid_ident(s):
  return s and s.isprintable() and all( not c.isspace() for c in s )

def define_common_flask_stuff(app, name):
  if os.environ.get(name.upper() + "_HTTPS") == "force":
    @app.before_request
    def https_required():
      if request.scheme != "https":
        return redirect(request.url.replace("http:", "https:"), code = 301)
    @app.after_request
    def after_request_func(response):
      response.headers["Strict-Transport-Security"] = 'max-age=63072000'
      return response

  PASSWORD = os.environ.get(name.upper() + "_PASSWORD")
  if PASSWORD:
    @app.before_request
    def auth_required():
      auth = request.authorization
      if not auth or auth.password != PASSWORD:
        m = "Password required."
        return m, 401, { "WWW-Authenticate": 'Basic realm="'+m+'"' }

  @app.route("/status/<game>")
  def r_status(game):
    return jsonify(dict(tick = current_game(game)["tick"]))

  return app

# vim: set tw=70 sw=2 sts=2 et fdm=marker :
