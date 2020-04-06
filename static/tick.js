window.onload = () => {
  const f = () => {
    const r = new XMLHttpRequest()
    r.addEventListener("load", e => {
      if (r.status != 200) { return }
      const t = JSON.parse(r.responseText).tick
      if (t > config.tick) {
        document.getElementById("form0").submit()
      } else {
        setTimeout(f, config.POLL)
      }
    })
    r.open("GET", `/status/${ config.game }`)
    r.send()
  }
  setTimeout(f, config.POLL)
}
