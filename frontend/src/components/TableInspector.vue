<template>
  <div class="ti-wrap">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">
          Every table in the .xer, verbatim — audit what the file actually contains, not this app's interpretation.
          <template v-if="ermhdr.version"> P6 {{ ermhdr.version }} &middot; exported {{ ermhdr.export_date }}</template>
        </span>
      </div>
    </div>

    <div v-if="omitted" class="empty-state">
      The browser-cached copy of this schedule is too large to keep the raw tables.
      Re-upload the original .xer file to inspect them.
    </div>
    <div v-else-if="tableNames.length === 0" class="empty-state">No raw tables available for this file.</div>

    <div v-else class="ti-body">
      <!-- Table picker -->
      <div class="ti-list">
        <button
          v-for="name in tableNames"
          :key="name"
          class="ti-item"
          :class="{ active: name === selectedName }"
          @click="selectTable(name)"
        >
          <span class="ti-name">{{ name }}</span>
          <span class="ti-count">{{ tables[name].row_count.toLocaleString() }}</span>
        </button>
      </div>

      <!-- Table view -->
      <div class="ti-detail" v-if="table">
        <div class="ti-toolbar">
          <input v-model="filter" class="ti-filter" type="text" :placeholder="`Filter ${selectedName} rows…`" />
          <span class="ti-meta">
            {{ filteredRows.length.toLocaleString() }} of {{ table.row_count.toLocaleString() }} rows
            <template v-if="sortCol !== null"> &middot; sorted by {{ table.fields[sortCol] }} {{ sortDir > 0 ? '↑' : '↓' }}</template>
          </span>
          <button v-if="sortCol !== null || filter" class="ti-clear" @click="filter = ''; sortCol = null">Reset</button>
        </div>

        <div v-if="table.truncated" class="ti-truncated">
          ⚠ This table has {{ table.row_count.toLocaleString() }} rows; only the first {{ table.rows.length.toLocaleString() }} were kept.
        </div>

        <div v-if="filteredRows.length === 0" class="empty-state">
          No rows in {{ selectedName }} match “{{ filter }}”.
        </div>
        <div v-else class="ti-scroll">
          <table class="ti-table">
            <thead>
              <tr>
                <th v-for="(f, i) in table.fields" :key="f" @click="sortBy(i)" :class="{ sorted: sortCol === i }" :title="'Sort by ' + f">
                  {{ f }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in pageRows" :key="ri" @click="detailRow = row" title="Show full record" class="ti-row">
                <td v-for="(f, ci) in table.fields" :key="ci" :title="row[ci]">{{ row[ci] }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="ti-pager" v-if="pageCount > 1">
          <button :disabled="page === 0" @click="page--">&lsaquo; Prev</button>
          <span>Page {{ page + 1 }} / {{ pageCount }}</span>
          <button :disabled="page >= pageCount - 1" @click="page++">Next &rsaquo;</button>
        </div>
      </div>
    </div>

    <!-- Vertical record view -->
    <Transition name="detail-slide">
      <aside v-if="detailRow" class="detail-drawer">
        <div class="detail-header">
          <div>
            <div class="detail-code">{{ selectedName }} record</div>
          </div>
          <button class="detail-close" @click="detailRow = null" title="Close (Esc)">✕</button>
        </div>
        <table class="ti-record">
          <tbody>
            <tr v-for="(f, i) in table.fields" :key="f">
              <th>{{ f }}</th>
              <td>{{ detailRow[i] || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </aside>
    </Transition>
  </div>
</template>

<script>
const PAGE_SIZE = 200

export default {
  name: 'TableInspector',
  props: {
    data: { type: Object, required: true },
  },
  data() {
    return {
      selectedName: null,
      filter: '',
      sortCol: null,
      sortDir: 1,
      page: 0,
      detailRow: null,
    }
  },
  computed: {
    tables() {
      return this.data.raw_tables || {}
    },
    omitted() {
      return !!this.data.raw_tables_omitted
    },
    ermhdr() {
      return this.data.ermhdr || {}
    },
    tableNames() {
      // Preserve file order (object insertion order) — it mirrors the export sequence.
      return Object.keys(this.tables)
    },
    table() {
      return this.selectedName ? this.tables[this.selectedName] : null
    },
    filteredRows() {
      if (!this.table) return []
      let rows = this.table.rows
      const q = this.filter.trim().toLowerCase()
      if (q) rows = rows.filter(r => r.some(c => c && c.toLowerCase().includes(q)))
      if (this.sortCol !== null) {
        const c = this.sortCol
        const dir = this.sortDir
        rows = [...rows].sort((a, b) => {
          const x = a[c] || ''
          const y = b[c] || ''
          const nx = parseFloat(x)
          const ny = parseFloat(y)
          // Numeric-aware: only when both cells parse fully as numbers.
          if (!isNaN(nx) && !isNaN(ny) && String(nx) === x.trim() && String(ny) === y.trim()) {
            return (nx - ny) * dir
          }
          return x.localeCompare(y) * dir
        })
      }
      return rows
    },
    pageCount() {
      return Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE))
    },
    pageRows() {
      const start = Math.min(this.page, this.pageCount - 1) * PAGE_SIZE
      return this.filteredRows.slice(start, start + PAGE_SIZE)
    },
  },
  watch: {
    filter() {
      this.page = 0
    },
    tableNames: {
      immediate: true,
      handler(names) {
        if (names.length && (!this.selectedName || !names.includes(this.selectedName))) {
          // TASK is what a reviewer opens first; fall back to the file's first table.
          this.selectedName = names.includes('TASK') ? 'TASK' : names[0]
        }
      },
    },
  },
  mounted() {
    this._onKeydown = e => {
      if (e.key === 'Escape' && this.detailRow && this.$el.offsetParent !== null) this.detailRow = null
    }
    window.addEventListener('keydown', this._onKeydown)
    document.addEventListener('mousedown', this._onDocMousedown = e => {
      if (this.detailRow && this.$el.offsetParent !== null && !this.$el.contains(e.target)) this.detailRow = null
    })
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._onKeydown)
    document.removeEventListener('mousedown', this._onDocMousedown)
  },
  methods: {
    selectTable(name) {
      this.selectedName = name
      this.filter = ''
      this.sortCol = null
      this.page = 0
      this.detailRow = null
    },
    sortBy(i) {
      if (this.sortCol === i) {
        if (this.sortDir === 1) this.sortDir = -1
        else { this.sortCol = null; this.sortDir = 1 }
      } else {
        this.sortCol = i
        this.sortDir = 1
      }
      this.page = 0
    },
  },
}
</script>

<style scoped>
.ti-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
.empty-state { font: var(--text-small); color: var(--gray-700); padding: var(--space-4); }

.ti-body { display: grid; grid-template-columns: 220px 1fr; }
.ti-list { border-right: 1px solid var(--gray-300); display: flex; flex-direction: column; padding: var(--space-2); gap: 1px; align-content: start; }
.ti-item { display: flex; justify-content: space-between; align-items: center; gap: var(--space-2); text-align: left; background: none; border: none; border-radius: var(--radius-sm); padding: 6px var(--space-3); cursor: pointer; }
.ti-item:hover { background: var(--gray-100); }
.ti-item.active { background: var(--active-soft); }
.ti-name { font-family: var(--font-mono); font-weight: 600; font-size: 13px; color: var(--ink); }
.ti-item.active .ti-name { color: var(--active); }
.ti-count { font: var(--text-micro); font-family: var(--font-mono); color: var(--gray-700); }

.ti-detail { min-width: 0; display: flex; flex-direction: column; }
.ti-toolbar { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border-bottom: 1px solid var(--gray-300); flex-wrap: wrap; }
.ti-filter { flex: 1; min-width: 180px; max-width: 360px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 6px 10px; background: var(--white); }
.ti-meta { font: var(--text-small); color: var(--gray-700); }
.ti-clear { font: var(--text-micro); border: 1px solid var(--gray-300); background: var(--gray-100); padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer; color: var(--gray-700); }
.ti-truncated { font: var(--text-small); color: var(--near); background: var(--near-tint); padding: var(--space-2) var(--space-3); }

.ti-scroll { overflow-x: auto; max-height: calc(100dvh - 350px); overflow-y: auto; }
.ti-table { border-collapse: collapse; font-size: 13px; min-width: 100%; }
.ti-table th { position: sticky; top: 0; background: var(--gray-100); font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); text-align: left; padding: 6px 10px; border-bottom: 2px solid var(--gray-300); white-space: nowrap; cursor: pointer; user-select: none; }
.ti-table th:hover { color: var(--ink); }
.ti-table th.sorted { color: var(--active); }
.ti-table td { font-family: var(--font-mono); padding: 4px 10px; border-bottom: 1px solid var(--gray-150); white-space: nowrap; max-width: 300px; overflow: hidden; text-overflow: ellipsis; color: var(--ink-soft); }
.ti-row { cursor: pointer; }
.ti-row:hover td { background: var(--accent-soft); }

.ti-pager { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); font: var(--text-small); color: var(--gray-700); }
.ti-pager button { border: 1px solid var(--gray-300); background: var(--gray-100); padding: 4px 12px; border-radius: var(--radius-sm); cursor: pointer; }
.ti-pager button:disabled { opacity: 0.4; cursor: default; }

.ti-record { width: 100%; border-collapse: collapse; font-size: 13px; }
.ti-record th { text-align: left; font-family: var(--font-mono); font-weight: 600; color: var(--gray-700); padding: 5px 8px 5px 0; vertical-align: top; white-space: nowrap; border-bottom: 1px solid var(--gray-150); }
.ti-record td { font-family: var(--font-mono); color: var(--ink); padding: 5px 0; border-bottom: 1px solid var(--gray-150); word-break: break-word; }

@media (max-width: 900px) {
  .ti-body { grid-template-columns: 1fr; }
  .ti-list { flex-direction: row; flex-wrap: wrap; border-right: none; border-bottom: 1px solid var(--gray-300); }
}
</style>
