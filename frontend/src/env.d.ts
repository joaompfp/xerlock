/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'local' builds the in-browser parser (Pyodide); anything else posts to /api/upload. */
  readonly VITE_PARSER?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
