// 主题初始化：必须在 Vue 应用挂载前同步执行，避免主题闪烁。
// 抽成外部脚本以避免 CSP 'unsafe-inline'（生产环境 script-src 不含 'unsafe-inline'）。
;(function () {
  var t = localStorage.getItem('luominest-theme')
  if (t !== 'dark') document.documentElement.setAttribute('data-theme', 'light')
})()
