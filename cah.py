#!/usr/bin/python3
# encoding: utf-8

# --                                                            ; {{{1
#
# File        : cah.py
# Maintainer  : Felix C. Stegerman <flx@obfusk.net>
# Date        : 2020-03-24
#
# Copyright   : Copyright (C) 2020  Felix C. Stegerman
# Version     : v0.0.1
# License     : AGPLv3+
#
# --                                                            ; }}}1

# NB: only works single-threaded!

# TODO:
# * select options
# * better game over handling
# * better error messages
# * use websocket instead of polling
# * (http) auth
# * leave game

import os, random, secrets

from flask import Flask, jsonify, request, render_template

# === logic ===

RANDOM    = 1
CARDS     = 10
POLL      = 1000
NIETZSCHE = -1  # "god is dead" (no czar)

OPACKS    = "blue fantasy geek green intl red science sf uk us".split()
UPACKS    = "unofficial-anime unofficial-anime-exp1".split()

if os.environ.get("CAHPY_PACKS"):
  packsets = dict(all = OPACKS + UPACKS, official = OPACKS,
                  unofficial = UPACKS)
  PACKS = [ p for k in os.environ.get("CAHPY_PACKS").split()
              for p in packsets.get(k, [k]) ]
else:
  PACKS = OPACKS

class InProgress(RuntimeError): pass
class OutOfCards(RuntimeError): pass
class InvalidVote(RuntimeError): pass
class InvalidParam(RuntimeError): pass

def blanks(s): return max(1, s.count("____"))

black_cards, white_cards = {}, {}
for pack in PACKS:
  with open("cards/black-" + pack) as f:
    for card in f: black_cards.setdefault(card, pack)
  with open("cards/white-" + pack) as f:
    for card in f: white_cards.setdefault(card, pack)
black, white = list(black_cards), list(white_cards)

def select_cards(packs):
  blk = set( i for i, card in enumerate(black)
               if black_cards[card] in packs )
  wht = set( i for i, card in enumerate(white)
               if white_cards[card] in packs )
  return blk, wht

# global state
games = {}

def current_game(game):
  return games[game]

def restart_game(game):
  del games[game]

def update_game(game, new):
  cur = current_game(game)
  cur.update(new, tick = cur["tick"] + 1)

def valid_ident(s):
  return s and s.isprintable() and all( not c.isspace() for c in s )

def get_random1(x):
  return random.sample(x, 1)[0]

# NB: takes min(n, len)
def take_random(s, n, empty_ok = False, less_ok = True):
  if not less_ok and len(s) < n: raise OutOfCards("not enough")
  if not s and not empty_ok: raise OutOfCards("empty")
  t = set(random.sample(s, min(n, len(s))))
  return t, s - t

def next_czar(cur):
  n = len(cur["players"])
  return 0 if cur["czar"] is None else (cur["czar"] + 1) % n

def init_game(game, name, nietzsche = False, packs = None):
  if game not in games:
    blk, wht  = select_cards(set(packs or PACKS))
    czar      = NIETZSCHE if nietzsche else None
    games[game] = dict(
      blk = blk, wht = wht, players = [], cards = {}, points = {},
      czar = czar, card = None, blanks = None, rand_ans = [],
      answers = {}, votes = {}, msg = None, prev = None, tick = 0
    )
  cur = current_game(game)
  if name not in cur["players"]:
    if cur["card"]: raise InProgress()  # in progress -> can't join
    hand, wht = take_random(cur["wht"], CARDS, less_ok = False)
    return dict(
      players = cur["players"] + [name],
      cards   = { **cur["cards"], name: hand },
      points  = { **cur["points"], name: 0 },
      wht     = wht
    )
  return None

def start_round(cur, game):
  czar      = NIETZSCHE if cur["czar"] == NIETZSCHE else next_czar(cur)
  cds, blk  = take_random(cur["blk"], 1); card = cds.pop()
  bla, wht  = blanks(black[card]), cur["wht"]
  rand_ans  = []
  for _ in range(min(RANDOM, len(wht) // bla)):
    ans, wht = take_random(wht, bla, less_ok = False)
    rand_ans.append((None, ans))
  if any( len(c) < bla for c in cur["cards"].values() ):
    raise OutOfCards("empty hand")  # some players w/o cards -> done
  res = dict(
    czar = czar, card = card, blk = blk, blanks = bla,
    rand_ans = rand_ans, answers = {}, votes = {},
    msg = None, prev = None
  )
  if bla > 2:
    res["cards"] = cur["cards"].copy()
    for hand in res["cards"].values():
      new, wht = take_random(wht, bla - 1, empty_ok = True)
      hand |= new
  res["wht"] = wht
  return res

def play_cards(cur, name, cards, discard = None):
  old = set(cards)
  if discard is not None: old.add(discard)
  new, wht = take_random(cur["wht"], len(old), empty_ok = True)
  hand = (cur["cards"][name] - old) | new
  return dict(
    cards   = { **cur["cards"], name: hand },
    answers = { **cur["answers"], name: cards },
    wht     = wht
  )

def choose_answer(cur, name, cards):
  winner = ([ k for k, v in cur["answers"].items()
                if set(cards) == set(v) ] + [None])[0]
  new = dict(card = None, prev = dict(
    card = cur["card"], answers = answer_data(cur)
  ))
  if winner == name: raise InvalidVote("vote for own answer")
  if cur["czar"] == NIETZSCHE:
    votes = { **cur["votes"], name: winner }
    if len(votes) == len(cur["players"]):
      pts = cur["points"].copy()
      for p in votes.values():
        if p is not None: pts[p] += 1
      return dict(votes = votes, points = pts, **new)
    else:
      return dict(votes = votes)
  else:
    if winner:
      pts = { **cur["points"], winner: cur["points"][winner] + 1 }
      msg = "Winner: {}.".format(winner)
      return dict(points = pts, msg = msg, **new)
    else:
      return dict(msg = "rand() won.", **new)

def player_data(cur):
  return ", ".join( p + ("*" if cur["czar"] == i else "")
                      + " (" + str(cur["points"][p]) + ")"
                      for i, p in enumerate(sorted(cur["players"])) )

def answer_data(cur):
  ans = cur["rand_ans"] + list(cur["answers"].items())
  random.Random(cur["card"]).shuffle(ans)
  return ans

def data(cur, game, name):
  n, nietzsche  = len(cur["players"]), cur["czar"] == NIETZSCHE
  done          = len(cur["answers"]) == (n if nietzsche else n-1)
  votes_for     = lambda p: list(cur["votes"].values()).count(p)
  return dict(
    cur = cur, game = game, name = name, players = player_data(cur),
    you_czar = cur["czar"] == cur["players"].index(name),
    nietzsche = nietzsche, card = cur["card"],
    answers = answer_data(cur) if done else None,
    votes_for = votes_for, complete = done, msg = cur["msg"],
    prev = cur["prev"], tick = cur["tick"],
    black = black, white = white, POLL = POLL
  )

def game_over(cur, game, name):
  return render_template(
    "done.html", game = game, name = name, players = player_data(cur)
  )

# === http ===

app = Flask(__name__)

@app.route("/")
def index():
  game = request.args.get("game") or secrets.token_hex(10)
  join = "join" in request.args
  return render_template("index.html", game = game, join = join,
                                       packs = PACKS)

@app.route("/status/<game>")
def status(game):
  cur = current_game(game)
  return jsonify(dict(tick = cur["tick"]))

@app.route("/play", methods = ["POST"])
def play():
  game, name  = request.form.get("game") , request.form.get("name")
  card, answ  = request.form.get("card0"), request.form.get("answ")
  nietzsche   = request.form.get("nietzsche")
  packs       = request.form.getlist("pack")
  try:
    if not valid_ident(game): raise InvalidParam("game")
    if not valid_ident(name): raise InvalidParam("name")
    if request.form.get("restart"): restart_game(game)
    pks = set(packs) & set(PACKS) if packs else None
    new = init_game(game, name, nietzsche, pks)
    if new: update_game(game, new)
    cur = current_game(game)
    if request.form.get("start") and cur["card"] is None:
      update_game(game, start_round(cur, game))
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
        new = choose_answer(cur, name, cards)
      else:
        rm = request.form.get("cardd")
        if rm and not rm.isdigit(): raise InvalidParam("cardd")
        new = play_cards(cur, name, cards, int(rm) if rm else None)
      update_game(game, new)
    return render_template("play.html", **data(cur, game, name))
  except InProgress:
    return render_template("late.html", game = game)
  except OutOfCards:
    return game_over(current_game(game), game, name)
  except InvalidVote as e:
    return render_template("error.html", error = e.args[0]), 400
  except InvalidParam as e:
    error = "invalid parameter: {}".format(e.args[0])
    return render_template("error.html", error = error), 400

# vim: set tw=70 sw=2 sts=2 et fdm=marker :
