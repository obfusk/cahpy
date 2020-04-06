document.getElementsByName("action").forEach(b => {
  if (b.form.id == "form0") {
    b.onclick = e => {
      const q = `Are you sure you want to ${b.value} the game?`
      if (!window.confirm(q)) { e.preventDefault() }
    }
  }
})
