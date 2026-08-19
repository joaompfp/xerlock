// Fullscreen behaviour shared by the Gantt and the network diagram.
//
// Both charts had an identical copy of this: the `isFullscreen` flag, the toggle,
// and — the part worth centralising — the document listener that must be added on
// mount and removed on unmount. A missed removal leaks a listener that fires
// against a dead component; this file makes that impossible to get wrong twice.
//
// The host component needs a `wrapEl` ref on the element to present, and may
// define `onFullscreenChanged()` to react (the network diagram re-fits its
// viewport, the Gantt doesn't need to).

export default {
  data() {
    return { isFullscreen: false }
  },
  mounted() {
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
  },
  beforeUnmount() {
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
  },
  methods: {
    toggleFullscreen() {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else if (this.$refs.wrapEl?.requestFullscreen) {
        this.$refs.wrapEl.requestFullscreen()
      }
    },
    onFullscreenChange() {
      // Driven by the document event rather than set in toggleFullscreen, so
      // leaving fullscreen via Esc or the browser chrome stays in sync.
      this.isFullscreen = !!document.fullscreenElement
      this.onFullscreenChanged?.()
    },
  },
}
