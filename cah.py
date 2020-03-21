import random

from flask import Flask, jsonify, request, render_template

RANDOM  = 1
CARDS   = 10

def n_blanks(s):
  return s.count("____")

# TODO: multiple blanks, other cards
with open("black") as f:
  black = list( x for x in f if n_blanks(x) == 1 )

with open("white") as f:
  white = list(f)

# NB: single-threaded!
games = {}

def init_game(game, name):
  if game not in games:
    games[game] = dict(
      black = set(range(len(black))), white = set(range(len(white))),
      players = set(), cards = {}, points = {}, card = None,
      czar = None, rand_ans = [], answers = {}, msg = None, tick = 0
    )
  cur = games[game]
  if name not in cur["players"]:
    if cur["czar"]: return None
    cur["players"].add(name)
    cards = set(random.sample(cur["white"], CARDS))
    cur["white"] -= cards
    cur["cards"][name] = cards
    cur["tick"] += 1
  return cur

def start_round(cur, game):
  if len(cur["black"]) == 0 or len(cur["white"]) == 0:
    return False
  for v in cur["cards"].values():
    if len(v) == 0: return False

  cur["czar"] = random.sample(cur["players"] - set([cur["czar"]]), 1)[0]
  cur["card"] = random.sample(cur["black"], 1)[0]
  cur["black"].remove(cur["card"])
  rand = random.sample(cur["white"], RANDOM)
  cur["white"] -= set(rand)
  cur["rand_ans"] = [ [x] for x in rand ]
  cur["answers"] = {}
  cur["msg"] = None
  cur["tick"] += 1

  return True

def play_cards(cur, name, cards):
  new = set(random.sample(cur["white"], len(cards)))
  cur["white"] -= new
  cur["cards"][name] -= set(cards)
  cur["cards"][name] |= new
  cur["answers"][name] = cards
  cur["tick"] += 1

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

app = Flask(__name__)

@app.route("/")
def index():
  game = request.args.get("game", "")
  return render_template("index.html", game = game)

@app.route("/status/<game>")
def status(game):
  return jsonify(dict(tick = games[game]["tick"]))

# TODO: websocket
@app.route("/play", methods = ["POST"])
def play():
  game = request.form.get("game")
  name = request.form.get("name")
  card = request.form.get("card")

  if request.form.get("restart"):
    del games[game]

  cur = init_game(game, name)

  if cur is None:
    return render_template("late.html", game = game)

  if request.form.get("start") and cur["czar"] is None:
    if not start_round(cur, game):
      return render_template("done.html", game = game, name = name)
  elif card:
    if cur["czar"] == name:
      choose_answer(cur, [int(card)])
    else:
      play_cards(cur, name, [int(card)])

  ans = cur["rand_ans"] + list(cur["answers"].values())
  random.shuffle(ans)

  players = ", ".join([ p + ("*" if cur["czar"] == p else "") + " ("
                          + str(cur["points"].get(p, 0)) + ")"
                          for p in sorted(cur["players"]) ])

  # print("GAME:", cur) # DEBUG

  return render_template(
    "play.html", game = game, name = name, cur = cur,
    tick = cur["tick"], players = players,
    you_czar = cur["czar"] == name, card = cur["card"], answers = ans,
    complete = len(cur["answers"]) == len(cur["players"]) - 1,
    msg = cur["msg"], black = black, white = white
  )
