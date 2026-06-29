var Live2DCubismCore
function __loadCubismCore () {
  var s = document.createElement('script')
  s.src = 'luominest-avatar://cubism-core/live2dcubismcore.min.js'
  s.onload = function () { Live2DCubismCore = window.Live2DCubismCore }
  document.head.appendChild(s)
}
__loadCubismCore()
