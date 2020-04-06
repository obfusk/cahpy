document.getElementById("form").onsubmit = e => {
  const r = document.getElementsByClassName("radio")
  const s = (new Set(Array.from(r).filter(x => x.checked)
                     .map(x => x.value))).size
  if (s != config.blanks) {
    alert(`Please select ${config.blanks} (different) card(s).`)
    e.preventDefault()
  }
}
