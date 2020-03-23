<!-- {{{1 -->

    File        : README.md
    Maintainer  : Felix C. Stegerman <flx@obfusk.net>
    Date        : 2020-03-23

    Copyright   : Copyright (C) 2020  Felix C. Stegerman
    Version     : v0.0.1
    License     : AGPLv3+

<!-- }}}1 -->

<!-- TODO: badges -->

[![AGPLv3+](https://img.shields.io/badge/license-AGPLv3+-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)

## Description

cahpy - capybaras against humanity

Cahpy is a web-based clone of the card game "Cards Against Humanity"
with some "house rules" built-in.

## Installing

Just `git clone` :)

## Requirements

Python (>= 3.5) & Flask.

### Debian

```bash
$ apt install python3-flask
```

### pip

```bash
$ pip3 install --user Flask   # for Debian; on other OS's you may need
                              # pip instead of pip3 and/or no --user
```

## Running

### Flask

```bash
$ FLASK_APP=cah.py flask run
```

### Gunicorn

```bash
$ gunicorn cah:app
```

### Heroku

Just `git push` :)

NB: you'll need to set `WEB_CONCURRENCY=1` b/c it only works
single-theaded atm!

### Packs

You can set `CAHPY_PACKS` to override the default choice of packs
(which is all non-unofficial packs in `cards/`).

```bash
$ export CAHPY_PACKS="unofficial-anime unofficial-anime-exp1"
```

## License

### Code

© Felix C. Stegerman

[![AGPLv3+](https://www.gnu.org/graphics/agplv3-155x51.png)](https://www.gnu.org/licenses/agpl-3.0.html)

### Cards

(i.e. `cards/*`)

See [`cards/COPYING`](cards/COPYING).

© [Cards Against Humanity](https://www.cardsagainsthumanity.com)

[![CC-BY-NC-SA](https://licensebuttons.net/l/by-nc-sa/2.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/2.0/)

<!-- vim: set tw=70 sw=2 sts=2 et fdm=marker : -->
