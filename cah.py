#!/usr/bin/python3
# encoding: utf-8

# --                                                            ; {{{1
#
# File        : cah.py
# Maintainer  : Felix C. Stegerman <flx@obfusk.net>
# Date        : 2020-03-21
#
# Copyright   : Copyright (C) 2020  Felix C. Stegerman
# Version     : v0.0.1
# License     : GPLv3+
#
# --                                                            ; }}}1

# NB: only works single-threaded!

# TODO:
# * other cards
# * better game over handling
# * websocket?

import random, secrets

from flask import Flask, jsonify, request, render_template

# === logic ===

RANDOM  = 1
CARDS   = 10
POLL    = 1000

class OutOfCards(RuntimeError): pass

class InvalidParam(RuntimeError): pass

def blanks(s): return s.count("____")

with open("black") as f: black = list(f)
with open("white") as f: white = list(f)

# global state
games = {}

def valid_ident(s):
  return s and s.isprintable() and all( not c.isspace() for c in s )

def get_random1(x):
  return random.sample(x, 1)[0]

# NB: takes min(n, len(s))
def take_random(s, n, empty_ok = False, less_ok = True):
  if not less_ok and len(s) < n: raise OutOfCards()
  if not s and not empty_ok: raise OutOfCards()
  t = set(random.sample(s, min(n, len(s))))
  s -= t
  return t

def init_game(game, name):
  if game not in games:
    games[game] = dict(
      black = set(range(len(black))), white = set(range(len(white))),
      players = set(), cards = {}, points = {}, czar = None,
      card = None, rand_ans = [], answers = {}, msg = None, tick = 0
    )
  cur = games[game]
  if name not in cur["players"]:
    if cur["czar"]: return None   # in progress -> can't join
    cur["players"].add(name)
    cur["cards"][name] = take_random(cur["white"], CARDS)
    cur["tick"] += 1
  return cur

def start_round(cur, game):
  cur["czar"]     = get_random1(cur["players"] - set([cur["czar"]]))
  cur["card"]     = take_random(cur["black"], 1).pop()
  cur["blanks"]   = b = blanks(black[cur["card"]])
  cur["rand_ans"] = [
    take_random(cur["white"], b, less_ok = False)
      for _ in range(min(RANDOM, len(cur["white"]) // b))
  ]
  cur["answers"]  = {}
  cur["msg"]      = None
  cur["tick"]    += 1
  if not all( len(c) > b for c in cur["cards"].values() ):
    return False                  # some players w/o cards -> done
  return True

def play_cards(cur, name, cards):
  cur["cards"][name]  -= set(cards)
  cur["cards"][name]  |= take_random(cur["white"], len(cards), True)
  cur["answers"][name] = cards
  cur["tick"]         += 1

def choose_answer(cur, cards):
  winner = ([ k for k, v in cur["answers"].items()
                         if set(cards) == set(v) ] + [None])[0]
  if winner:
    cur["points"].setdefault(winner, 0)
    cur["points"][winner] += 1
    cur["msg"] = "Winner: {}.".format(winner)
  else:
    cur["msg"] = "The random card won."
  cur["card"] = cur["czar"] = None
  cur["tick"] += 1

def data(cur, game, name):
  ans = None
  com = len(cur["answers"]) == len(cur["players"]) - 1
  if com:
    ans = cur["rand_ans"] + list(cur["answers"].values())
    random.shuffle(ans)
  players = ", ".join([ p + ("*" if cur["czar"] == p else "") + " ("
                          + str(cur["points"].get(p, 0)) + ")"
                          for p in sorted(cur["players"]) ])
  return dict(
    cur = cur, game = game, name = name, players = players,
    you_czar = cur["czar"] == name, card = cur["card"],
    answers = ans, complete = com,
    msg = cur["msg"], tick = cur["tick"],
    black = black, white = white, POLL = POLL
  )

# === http ===

app = Flask(__name__)

@app.route("/")
def index():
  game = request.args.get("game") or secrets.token_hex(10)
  return render_template("index.html", game = game)

@app.route("/status/<game>")
def status(game):
  return jsonify(dict(tick = games[game]["tick"]))

@app.route("/play", methods = ["POST"])
def play():
  game, name = request.form.get("game"), request.form.get("name")
  card, answ = request.form.get("card0"), request.form.get("answ")
  if not valid_ident(game): raise InvalidParam("game")
  if not valid_ident(name): raise InvalidParam("name")
  try:
    if request.form.get("restart"): del games[game]
    cur = init_game(game, name)
    if cur is None:
      return render_template("late.html", game = game)
    if request.form.get("start") and cur["czar"] is None:
      if not start_round(cur, game):
        return render_template("done.html", game = game, name = name)
    elif card or answ:
      err = InvalidParam("answ" if answ else "card*")
      cds = card = answ.split(",") if answ else [
        request.form.get("card{}".format(i), "")
          for i in range(cur["blanks"])
      ]
      if not all( x.isdigit() for x in cds ): raise err
      cards = list(map(int, cds))
      if len(set(cards)) != cur["blanks"]: raise err
      if answ:
        choose_answer(cur, cards)
      else:
        play_cards(cur, name, cards)
  except OutOfCards as e:
    return render_template("done.html", game = game, name = name)
  # print("GAME:", cur) # DEBUG
  return render_template("play.html", **data(cur, game, name))

# vim: set tw=70 sw=2 sts=2 et fdm=marker :
