// Long lists that stop at ROW_LIMIT rows until "Show all" is asked for, shared by the
// health check's offender lists and the progress view's lists. On a large file a list
// in full is thousands of rows nobody scrolls through, drawn before anyone asks.
//
// The host renders `list.slice(0, rowLimit('name'))`, and under it a "Show all"
// control calling `showAllRows('name')` while `list.length > rowLimit('name')`.

import { defineComponent } from 'vue'

export const ROW_LIMIT = 100

export default defineComponent({
  data() {
    return {
      // Lists shown in full after "Show all".
      fullLists: [] as string[],
    }
  },
  methods: {
    rowLimit(list: string): number {
      return this.fullLists.includes(list) ? Infinity : ROW_LIMIT
    },
    showAllRows(list: string) {
      if (!this.fullLists.includes(list)) this.fullLists.push(list)
    },
  },
})
