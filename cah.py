#!/usr/bin/python3
# encoding: utf-8

# --                                                            ; {{{1
#
# File        : cah.py
# Maintainer  : Felix C. Stegerman <flx@obfusk.net>
# Date        : 2020-04-17
#
# Copyright   : Copyright (C) 2020  Felix C. Stegerman
# Version     : v0.0.1
# License     : AGPLv3+
#
# --                                                            ; }}}1

# NB: only works single-threaded!

# TODO:
# * better game over handling
# * better error messages
# * use websocket instead of polling

import json, os, random, secrets

import jinja2

from flask import Flask, redirect, request, render_template, url_for

from obfusk.webgames.common import *

# === logic ===

HANDSIZE  = 13
RANDOMS   = 1

NIETZSCHE = -1  # "god is dead" (no czar)

OPACKS, UPACKS = [], []
for f in sorted(os.listdir("cards")):
  if not f.endswith("~") and f.startswith("black-"):
    (UPACKS if "uno-" in f else OPACKS).append(f[6:])

if os.environ.get("CAHPY_PACKS"):
  packsets = dict(all = OPACKS + UPACKS, official = OPACKS,
                  unofficial = UPACKS)
  PACKS = [ p for k in os.environ.get("CAHPY_PACKS").split()
              for p in packsets.get(k, [k]) ]
else:
  PACKS = OPACKS

class OutOfCards(Oops): pass

def blanks(s): return max(1, s.count("____"))

def esc(s):
  return str(jinja2.escape(s)).replace("[i]" , "<i>"   ) \
                              .replace("[/i]", "</i>"  ) \
                              .replace("[br]", "<br/>" )

# load cards from disk
black_cards, white_cards = {}, {}
for pack in PACKS:
  with open("cards/black-" + pack) as f:
    for card in f: black_cards.setdefault(esc(card), set()).add(pack)
  with open("cards/white-" + pack) as f:
    for card in f: white_cards.setdefault(esc(card), set()).add(pack)
black, white = tuple(black_cards), tuple(white_cards)

def select_cards(packs):
  blk = set( i for i, card in enumerate(black)
               if black_cards[card] & packs )
  wht = set( i for i, card in enumerate(white)
               if white_cards[card] & packs )
  return blk, wht

def pack_for(cur, colour, card):
  cs = (black_cards[black[card]] if colour == "black" else
        white_cards[white[card]])
  return next(iter(cs & cur["packs"])).replace("uno-", "")

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

def init_game(game, name, nietzsche = False, packs = None,
              handsize = None, randoms = None):
  if game not in games:
    if handsize is None: handsize = HANDSIZE
    if randoms is None: randoms = RANDOMS
    pks       = set(packs or PACKS)
    blk, wht  = select_cards(pks)
    czar      = NIETZSCHE if nietzsche else None
    games[game] = dict(
      blk = blk, wht = wht, players = [], cards = {}, points = {},
      czar = czar, card = None, blanks = None, rand_ans = [],
      answers = {}, votes = {}, msg = None, prev = None, tick = 0,
      handsize = handsize, randoms = randoms, packs = pks
    )
  cur = current_game(game)
  if name not in cur["players"]:
    if cur["card"]: raise InProgress()    # in progress -> can't join
    new       = dict(players = cur["players"] + [name])
    if name in cur["points"]: return new  # rejoin
    hand, wht = take_random(cur["wht"], cur["handsize"], less_ok = False)
    cards     = { **cur["cards"], name: hand }
    points    = { **cur["points"], name: 0 }
    return dict(cards = cards, points = points, wht = wht, **new)
  return None

def leave_game(game, name):
  cur = current_game(game)
  if cur["card"]: raise InProgress()      # in progress -> can't leave
  players = [ p for p in cur["players"] if p != name ]
  return dict(players = players)

def start_round(cur):
  czar      = NIETZSCHE if cur["czar"] == NIETZSCHE else next_czar(cur)
  cds, blk  = take_random(cur["blk"], 1); card = cds.pop()
  bla, wht  = blanks(black[card]), cur["wht"]
  rand_ans  = []
  for i in range(min(cur["randoms"], len(wht) // bla)):
    ans, wht = take_random(wht, bla, less_ok = False)
    rand_ans.append((i, ans))
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
  if name in cur["answers"]: raise InvalidAction("already answered")
  old = set(cards)
  if discard is not None: old.add(discard)
  hand = cur["cards"][name] - old
  new, wht = take_random(cur["wht"], cur["handsize"] - len(hand),
                         empty_ok = True)
  return dict(
    cards   = { **cur["cards"], name: hand | new },
    answers = { **cur["answers"], name: cards },
    wht     = wht
  )

def choose_answer(cur, name, cards):
  f = lambda s: [ k for k, v in s if set(cards) == set(v) ]
  new = dict(card = None, prev = dict(
    card = cur["card"], answers = answer_data(cur)
  ))
  winner = (f(cur["answers"].items()) + [None])[0]
  if winner == name: raise InvalidAction("vote for own answer")
  if cur["czar"] == NIETZSCHE:
    if name in cur["votes"]: raise InvalidAction("already voted")
    votes = { **cur["votes"], name: winner or f(cur["rand_ans"])[0] }
    if len(votes) == len(cur["players"]):
      pts = cur["points"].copy()
      for p in votes.values():
        if isinstance(p, str): pts[p] += 1
      return dict(votes = votes, points = pts, **new)
    else:
      return dict(votes = votes)
  else:
    if cur["czar"] != name: raise InvalidAction("not the czar")
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
  votes_for     = lambda p: tuple(cur["votes"].values()).count(p)
  return dict(
    cur = cur, game = game, name = name, players = player_data(cur),
    you_czar = cur["czar"] == cur["players"].index(name),
    nietzsche = nietzsche, card = cur["card"],
    answers = answer_data(cur) if done else None,
    votes_for = votes_for, complete = done, msg = cur["msg"],
    prev = cur["prev"], pack_for = pack_for,
    black = black, white = white,
    config = json.dumps(dict(game = game, tick = cur["tick"],
                             blanks = cur["blanks"], POLL = POLL))
  )

def game_over(cur, game, name):
  return render_template(
    "done.html", game = game, name = name, players = player_data(cur)
  )

# === http ===

app = define_common_flask_stuff(Flask(__name__), "cahpy")

@app.route("/")
def r_index():
  args = request.args
  game = args.get("game") or secrets.token_hex(10)
  return render_template(
    "index.html", game = game, name = args.get("name"),
    join = "join" in args, packs = PACKS, handsize = HANDSIZE,
    randoms = RANDOMS
  )

@app.route("/play", methods = ["POST"])
def r_play():
  form              = request.form
  action            = form.get("action")
  game, name        = form.get("game")      , form.get("name")
  card, answ        = form.get("card0")     , form.get("answ")
  nietzsche, packs  = form.get("nietzsche") , form.getlist("pack")
  handsize          = form.get("handsize" , type = int)
  randoms           = form.get("randoms"  , type = int)
  try:
    if not valid_ident(game): raise InvalidParam("game")
    if not valid_ident(name): raise InvalidParam("name")
    if action in "leave restart rejoin".split():
      if action == "leave":
        update_game(game, leave_game(game, name))
      elif action == "restart":
        restart_game(game)
      return redirect(url_for(
        "r_index", join = "yes" if action != "restart" else None,
        game = game, name = name
      ))
    pks = set(packs) & set(PACKS) if packs else None
    new = init_game(game, name, nietzsche, pks, handsize, randoms)
    if new: update_game(game, new)
    cur = current_game(game)
    if action == "start" and cur["card"] is None:
      update_game(game, start_round(cur))
    elif card or answ:
      err = InvalidParam("answ" if answ else "card*")
      cds = card = answ.split(",") if answ else [
        form.get("card{}".format(i), "") for i in range(cur["blanks"])
      ]
      if not all( x.isdigit() for x in cds ): raise err
      cards = tuple(map(int, cds))
      if len(set(cards)) != cur["blanks"]: raise err
      if answ:
        new = choose_answer(cur, name, cards)
      else:
        rm = form.get("cardd")
        if rm and not rm.isdigit(): raise InvalidParam("cardd")
        new = play_cards(cur, name, cards, int(rm) if rm else None)
      update_game(game, new)
    return render_template("play.html", **data(cur, game, name))
  except InProgress:
    return render_template("late.html", game = game)
  except OutOfCards:
    return game_over(current_game(game), game, name)
  except Oops as e:
    d = dict(game = game if valid_ident(game) else None,
             name = name if valid_ident(name) else None)
    return render_template("error.html", error = e.msg(), **d), 400

# vim: set tw=70 sw=2 sts=2 et fdm=marker :
