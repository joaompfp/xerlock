import { createApp } from 'vue'
// Fonts are bundled, not fetched from a font CDN: a self-hosted review tool should make
// no third-party requests (each would disclose the viewer's IP to that party).
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans/700.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import '@fontsource/ibm-plex-mono/700.css'
import './styles/sections.css'
import './styles/popover.css'
import App from './App.vue'

createApp(App).mount('#app')
