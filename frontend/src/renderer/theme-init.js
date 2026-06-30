(function () {
  var t = localStorage.getItem('luominest-theme')
  if (t !== 'dark') document.documentElement.setAttribute('data-theme', 'light')
})()
