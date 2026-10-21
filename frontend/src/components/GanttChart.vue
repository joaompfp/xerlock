<template>
  <div class="gantt-wrap" :class="{ 'is-fullscreen': isFullscreen }" ref="wrapEl">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">{{ data.project.total_activities }} activities</span>
      </div>
      <!-- The bar encoding is stated once, here, rather than in the toolbar. -->
      <div class="legend">
        <template v-if="criticalBasis === 'tf0'">
          <span class="legend-item"><i class="lg-bar lg-critical"></i>Critical (TF&le;0)</span>
          <span class="legend-item"><i class="lg-bar lg-near"></i>Near-critical</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <template v-else>
          <span class="legend-item"><i class="lg-bar lg-critical"></i>On longest path</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <span class="legend-item"><i class="lg-bar lg-negative"></i>Negative float</span>
        <span class="legend-item"><i class="diamond"></i>Milestone</span>
        <span class="legend-item"><i class="bar-wbs"></i>WBS rollup</span>
        <span class="legend-item" v-if="baseline && showBaseline"><i class="lg-bar lg-ghost"></i>Baseline</span>
      </div>
    </div>

    <!-- One toolbar row, ordered by frequency of use. What is used once per session
         (Today, Fullscreen, Print, paper size) lives behind the overflow. -->
    <div class="gantt-toolbar">
      <div class="zoom-group">
        <button
          v-for="z in zoomLevels"
          :key="z"
          :class="{ active: !dayWidthOverride && zoom === z }"
          @click="selectZoomPreset(z)"
        >{{ zoomLabel(z) }}</button>
      </div>
      <div class="zoom-adjust">
        <button class="zbtn" title="Zoom out" @click="zoomOut">−</button>
        <button class="zbtn" title="Fit to available width" @click="fitToWidth">Fit</button>
        <button class="zbtn" title="Zoom in" @click="zoomIn">+</button>
      </div>

      <span class="tb-div"></span>

      <div class="tb-group">
        <span class="tb-group-label">WBS</span>
        <button class="ctrl-btn" @click="expandAll">Expand</button>
        <button class="ctrl-btn" title="Expand one more WBS level" @click="expandOneLevel">+1</button>
        <button class="ctrl-btn" title="Collapse the deepest expanded WBS level" @click="collapseOneLevel">−1</button>
        <button class="ctrl-btn" @click="collapseAll">Collapse</button>
      </div>

      <span class="tb-div"></span>

      <div class="tb-group basis-group">
        <span class="tb-group-label">Basis</span>
        <button :class="{ active: criticalBasis === 'tf0' }" @click="criticalBasis = 'tf0'">TF &le; 0</button>
        <button :class="{ active: criticalBasis === 'longest' }" @click="criticalBasis = 'longest'">Longest path</button>
      </div>

      <span class="tb-div"></span>

      <!-- Overlay chips: solid border with a dot when on, dashed when off. -->
      <button class="tb-chip" :class="{ on: showLinks }" @click="showLinks = !showLinks"><i></i>Links</button>
      <select v-if="showLinks" v-model="linksScope" class="filter-select linkscope-select" title="Which relationships to draw">
        <option value="critical">Critical only</option>
        <option value="all">All logic</option>
      </select>
      <button class="tb-chip" :class="{ on: showProgressLine }" @click="showProgressLine = !showProgressLine"><i></i>Progress line</button>
      <button v-if="baseline" class="tb-chip" :class="{ on: showBaseline }" @click="showBaseline = !showBaseline" title="Ghost bars at each activity's position in the compared snapshot"><i></i>Baseline</button>

      <div class="tb-right">
        <div class="tb-pop">
          <button class="ctrl-btn tb-more" @click="overflowOpen = !overflowOpen" :aria-expanded="(String(overflowOpen) as 'true' | 'false')" title="More actions" aria-label="More actions">⋯</button>
          <div v-if="overflowOpen" class="tb-panel tb-panel-menu">
            <button :disabled="todayX === null" @click="overflowOpen = false; scrollToToday()">Scroll to today</button>
            <button @click="overflowOpen = false; toggleFullscreen()">{{ isFullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</button>
            <div class="fp-sep"></div>
            <label class="fp-row"><span>Paper</span>
              <select v-model="printPaperSize" class="filter-select">
                <option v-for="(p, key) in paperSizes" :key="key" :value="key">{{ p.label }}</option>
              </select>
            </label>
            <button @click="overflowOpen = false; printGantt()">Print</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Every filter sits on this one row, and a control that is narrowing the view is
         drawn in the accent colour, so a filtered chart can't be read as the whole programme. -->
    <div class="filter-strip">
      <span class="fs-label">FILTER</span>
      <input type="text" v-model="filterText" class="filter-input fb-search" :class="{ set: filterText.trim() }" placeholder="Search…" title="Search activity code, name or WBS path" />
      <select v-model="filterStatus" class="fb-select" :class="{ set: filterStatus }" title="Status">
        <option value="">Status</option>
        <option value="TK_NotStart">Not started</option>
        <option value="TK_Active">Active</option>
        <option value="TK_Complete">Complete</option>
      </select>
      <select v-model="filterConstraint" class="fb-select" :class="{ set: filterConstraint }" title="Constraint">
        <option value="">Constraint</option>
        <option v-for="o in constraintFilterOptions" :key="o.value" :value="o.value" :disabled="o.count === 0">{{ o.label }} ({{ o.count }})</option>
      </select>
      <select v-model="filterNotes" class="fb-select" :class="{ set: filterNotes }" title="Your review notes (the dot after an activity's name)">
        <option value="">Notes</option>
        <option v-for="o in noteFilterOptions" :key="o.value" :value="o.value" :disabled="o.count === 0">{{ o.label }} ({{ o.count }})</option>
      </select>
      <button class="tb-chip" :class="{ on: filterCriticalOnly }" @click="filterCriticalOnly = !filterCriticalOnly" title="Critical activities only, on the current basis"><i></i>Critical</button>
      <span class="fb-dates" :class="{ set: filterFrom || filterTo }" title="Date window: activities touching it">
        <input type="date" v-model="filterFrom" class="filter-date" aria-label="From" />
        <span class="fb-dash">–</span>
        <input type="date" v-model="filterTo" class="filter-date" aria-label="To" />
      </span>
      <template v-if="data.project.data_date">
        <button class="btn-tiny-light la-btn" :class="{ active: lookAheadActive(28) }" title="Data date + 4 weeks" @click="setLookAhead(28)">4 wk</button>
        <button class="btn-tiny-light la-btn" :class="{ active: lookAheadActive(56) }" title="Data date + 8 weeks" @click="setLookAhead(56)">8 wk</button>
      </template>
      <select v-if="codeTypesAvailable.length" class="fb-select" title="P6 activity codes, read verbatim from this file's ACTVTYPE table" @change="addCodeFilter">
        <option value="">Activity code</option>
        <optgroup v-for="t in codeTypesAvailable" :key="t" :label="t">
          <option v-for="c in codeValuesByType.get(t)" :key="c" :value="JSON.stringify([t, c])">{{ c }}</option>
        </optgroup>
      </select>
      <button v-for="[type, code] in activeCodeFilters" :key="type" class="fs-chip" @click="clearFilter('code:' + type)" :title="`Remove: ${type}: ${code}`">
        {{ type }}: {{ code }}<span class="fs-x">&times;</span>
      </button>
      <button v-if="activeFilterChips.length" class="btn-tiny-light" @click="clearFilters">Clear</button>
      <button v-if="returnTab" class="return-chip" @click="$emit('return-to-origin')">&larr; Back to {{ returnTab }}</button>
      <span v-if="isolatedIds" class="isolation-chip">
        Chain trace &middot; {{ isolatedIds.size }} {{ isolatedIds.size === 1 ? 'activity' : 'activities' }}
        <button class="isolation-exit" @click="exitIsolation">Show all</button>
      </span>
      <span class="filter-count" title="Activities shown">{{ matchCount }} of {{ data.activities.length }}</span>
    </div>

    <div class="gantt-body">
    <div
      class="gantt-scroll"
      :class="{ panning }"
      ref="scrollEl"
      @scroll="onScroll"
      @wheel="onWheel"
      @mousedown="onPanStart"
    >
      <!-- Filters can exclude everything; without this the chart is a blank
           rectangle and the user cannot tell it apart from a failure. -->
      <div v-if="rows.length === 0" class="g-empty">
        <p class="g-empty-title">No activities match the current filters.</p>
        <p class="g-empty-sub">{{ emptyFilterHint }}</p>
        <button class="btn-tiny-light" @click="clearFilters">Clear filters</button>
      </div>
      <!-- One grid per page: on screen a single page holds every row; a printout gets one
           grid per sheet, each with its own header and a slice of the rows (gridPages). -->
      <template v-for="(pg, pi) in gridPages" :key="pg.start">
      <div v-if="!pg.screen" class="print-title">
        <strong>{{ data.project.proj_short_name }}</strong>
        <span v-if="data.project.data_date">Data date {{ formatDate(data.project.data_date) }}</span>
        <span v-if="activeFilterChips.length">Filtered: {{ activeFilterChips.map(c => c.label).join(', ') }}</span>
        <span v-if="isolatedIds">Chain trace: {{ isolatedIds.size }} {{ isolatedIds.size === 1 ? 'activity' : 'activities' }}</span>
        <span v-if="showSlip">Compared with {{ baselineFilename || 'the loaded baseline' }}: outlined bars, Slip in calendar days</span>
        <span class="print-pageno">Page {{ pi + 1 }} of {{ gridPages.length }}</span>
      </div>
      <div
        class="gantt-grid"
        :class="{ 'gantt-print-page': !pg.screen, 'gantt-print-last': !pg.screen && pi === gridPages.length - 1 }"
        :style="{ gridTemplateColumns: labelColWidth + 'px ' + totalWidth + 'px', width: (labelColWidth + totalWidth) + 'px', height: (HEADER_HEIGHT + pg.bodyHeight) + 'px' }"
      >
        <!-- Header + label column are positioned manually (top/left tracked from the @scroll
             handler) instead of using position:sticky — Chromium mis-renders sticky grid items
             whose own box exactly fills a narrow track once you scroll near the content's end. -->
        <div class="g-cell g-corner" :style="{ top: pg.top + 'px', left: pg.left + 'px', width: labelColWidth + 'px' }">
          <span class="g-corner-name">Activity</span>
          <span class="g-col-dur g-corner-col">Dur</span>
          <span class="g-col-date g-corner-col">Start</span>
          <span class="g-col-date g-corner-col">Finish</span>
          <span class="g-col-float g-corner-col">Float</span>
          <span v-if="showSlip" class="g-col-slip g-corner-col" title="Finish slippage against the compared schedule, in calendar days: + later, &minus; earlier">Slip</span>
        </div>
        <div class="g-cell g-timeline-header" :style="{ top: pg.top + 'px', left: labelColWidth + 'px', width: totalWidth + 'px' }">
          <div class="g-header-band-row">
            <div
              v-for="t in bandTicks"
              :key="'b' + t.x"
              class="g-band-tick"
              :style="{ left: t.x + 'px' }"
            >{{ t.label }}</div>
            <!-- The data date labelled where the eye starts reading the timeline -->
            <span
              v-if="ddX(pg) !== null"
              class="g-dd-chip"
              :style="{ left: ddX(pg) + 'px' }"
              :title="'Data date: ' + formatDate(data.project.data_date)"
            >{{ formatDateShort(data.project.data_date) }} &middot; data date</span>
          </div>
          <div class="g-header-detail-row">
            <div
              v-for="t in detailTicks"
              :key="'d' + t.x"
              class="g-detail-tick"
              :class="{ weekend: t.weekend }"
              :style="{ left: t.x + 'px' }"
            >{{ t.label }}</div>
          </div>
        </div>

        <!-- Background layer: weekend shading + gridlines — sits BELOW bars -->
        <svg
          class="g-overlay g-overlay-bg"
          :style="{ left: labelColWidth + 'px', top: HEADER_HEIGHT + 'px', width: totalWidth + 'px', height: pg.bodyHeight + 'px' }"
          :width="totalWidth"
          :height="pg.bodyHeight"
        >
          <rect
            v-for="r in weekendRects"
            :key="'we' + r.x"
            :x="r.x" y="0" :width="r.w" :height="pg.bodyHeight"
            class="g-weekend"
          />
          <line
            v-for="t in detailTicks"
            :key="'gl' + t.x"
            :x1="t.x" :x2="t.x" y1="0" :y2="pg.bodyHeight"
            class="g-gridline"
          />
          <line
            v-for="t in secondaryMonthGridlines"
            :key="'glm' + t.x"
            :x1="t.x" :x2="t.x" y1="0" :y2="pg.bodyHeight"
            class="g-gridline-month"
          />
        </svg>

        <!-- Foreground layer: critical links + progress line — sits ABOVE bars, so a link never
             visually disappears behind an unrelated activity's bar. -->
        <svg
          class="g-overlay g-overlay-fg"
          :style="{ left: labelColWidth + 'px', top: HEADER_HEIGHT + 'px', width: totalWidth + 'px', height: pg.bodyHeight + 'px' }"
          :width="totalWidth"
          :height="pg.bodyHeight"
        >
          <defs>
            <marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L8 4L0 8z" class="g-link-arrow" />
            </marker>
            <marker id="gantt-arrow-chain" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L8 4L0 8z" class="g-link-arrow-chain" />
            </marker>
          </defs>
          <g :transform="'translate(0,' + (-pg.start * ROW_HEIGHT) + ')'">
          <path
            v-for="l in links"
            :key="l.id"
            :d="l.d"
            class="g-link"
            :class="{ 'g-link-chain': l.chain }"
            :marker-end="l.chain ? 'url(#gantt-arrow-chain)' : 'url(#gantt-arrow)'"
          />
          <path v-if="progressLinePath" :d="progressLinePath" class="g-progress-line" />
          <line
            v-for="c in calloutsOf(pg)"
            :key="'cl' + c.id"
            :x1="c.ax" :y1="c.ay" :x2="c.ax + c.dx" :y2="c.ay + c.dy + 9"
            class="g-callout-leader"
          />
          <circle
            v-for="(p, i) in progressLinePoints"
            :key="'pp' + i"
            :cx="p.x" :cy="p.y" r="2.5"
            class="g-progress-dot"
          />
          </g>
        </svg>

        <!-- Today line (above everything but the frozen header/label) -->
        <div
          v-if="pg.screen && todayX !== null"
          class="g-today-line"
          :style="{ left: (labelColWidth + todayX) + 'px', top: HEADER_HEIGHT + 'px', height: pg.bodyHeight + 'px' }"
        ><span class="g-today-flag">Today</span></div>

        <!-- Data date line: the schedule's own status date — the anchor every
             progress/forecast judgement should be made against, not "today". -->
        <div
          v-if="ddX(pg) !== null"
          class="g-dd-line"
          :style="{ left: (labelColWidth + ddX(pg)!) + 'px', top: HEADER_HEIGHT + 'px', height: pg.bodyHeight + 'px' }"
          :title="'Data date: ' + formatDate(data.project.data_date)"
        ></div>

        <!-- Resize handle for the label column, tracked against horizontal scroll manually
             (position:sticky inside a CSS-grid item gets unreliable with explicit track spans,
             so we just follow pg.left from the @scroll handler instead). -->
        <div
          v-if="pg.screen"
          class="g-resize-handle"
          :class="{ resizing }"
          :style="{ left: (pg.left + labelColWidth - 3) + 'px', height: (HEADER_HEIGHT + pg.bodyHeight) + 'px' }"
          @mousedown.stop="onResizeStart"
          @dblclick.stop="fitLabelColumn"
          title="Drag to resize; double-click to fit the names"
        ></div>

        <!-- Rows -->
        <template v-for="row in pg.rows" :key="row.key">
          <div
            class="g-cell g-label"
            :class="{ 'g-label-wbs': row.type === 'wbs', selected: row.type === 'activity' && row.activity.task_id === selectedTaskId }"
            :style="{ top: (HEADER_HEIGHT + (row.index - pg.start) * ROW_HEIGHT) + 'px', left: pg.left + 'px', width: labelColWidth + 'px', paddingLeft: (8 + row.level * 11) + 'px' }"
            @click="row.type === 'wbs' ? toggleWbs(row.wbsId) : selectActivity(row.activity)"
          >
            <template v-if="row.type === 'wbs'">
              <IconChevron class="g-toggle" :expanded="isFilterActive ? !filterCollapsed.has(row.wbsId) : expandedWbs.has(row.wbsId)" />
              <span class="g-wbs-name">{{ row.name }}</span>
              <span class="g-wbs-count">{{ row.count }}</span>
              <span class="g-col-dur"></span>
              <span class="g-col-date">{{ row.start ? formatDateShort(row.start) : '' }}</span>
              <span class="g-col-date">{{ row.finish ? formatDateShort(row.finish) : '' }}</span>
              <span class="g-col-float"></span>
              <span v-if="showSlip" class="g-col-slip" :class="wbsSlipCell(row).cls" :title="wbsSlipCell(row).title">{{ wbsSlipCell(row).text }}</span>
            </template>
            <template v-else>
              <button v-if="annotations[row.activity.task_id]" class="annotation-hit" :title="(annotations[row.activity.task_id].callout ? 'Hide' : 'Show') + ' note on the chart: ' + annotations[row.activity.task_id].note" @click.stop="toggleCallout(row.activity.task_id)"><i class="annotation-flag" :class="'sev-' + annotations[row.activity.task_id].severity"></i></button>
              <span class="g-act-code">{{ row.activity.task_code }}</span>
              <span class="g-act-name">{{ row.activity.task_name }}</span>
              <span class="g-col-dur">{{ formatHours(row.activity.duration_hrs, row.activity.calendar_hrs_per_day) }}</span>
              <span class="g-col-date">{{ formatDateShort(displayStart(row.activity)) }}</span>
              <span class="g-col-date">{{ formatDateShort(displayEnd(row.activity)) }}</span>
              <span class="g-col-float" :class="floatCellClass(row.activity)">{{ formatFloat(row.activity.total_float_hrs, row.activity.calendar_hrs_per_day) }}</span>
              <span v-if="showSlip" class="g-col-slip" :class="slipCell(row.activity).cls" :title="slipCell(row.activity).title">{{ slipCell(row.activity).text }}</span>
            </template>
          </div>
          <div
            class="g-cell g-timeline-row"
            :style="{ gridRow: (row.index - pg.start + 2), gridColumn: 2, width: totalWidth + 'px' }"
          >
            <div
              v-if="row.type === 'wbs'"
              class="g-bar-wbs"
              :style="wbsBarStyle(row)"
              :title="row.name + ' — ' + row.count + ' activities'"
            ></div>
            <template v-else-if="row.milestone">
              <div
                v-if="ghostFor(row.activity)"
                class="g-milestone-ghost"
                :style="{ left: ghostFor(row.activity)!.x + 'px' }"
                :title="'Baseline: ' + ghostFor(row.activity)!.label"
              ></div>
              <div
                class="g-milestone"
                :class="row.cls"
                :style="{ left: row.x + 'px' }"
                :title="milestoneTitle(row.activity)"
                @click="selectActivity(row.activity)"
              ></div>
            </template>
            <template v-else>
              <div
                v-if="ghostFor(row.activity)"
                class="g-bar-ghost"
                :style="{ left: ghostFor(row.activity)!.x + 'px', width: ghostFor(row.activity)!.w + 'px' }"
                :title="'Baseline: ' + ghostFor(row.activity)!.label"
              ></div>
              <div
                v-if="row.tailW"
                class="g-float-tail"
                :style="{ left: (row.x + row.w) + 'px', width: row.tailW + 'px' }"
                :title="'Float: ' + formatFloat(row.activity.total_float_hrs, row.activity.calendar_hrs_per_day)"
              ></div>
              <div
                class="g-bar"
                :class="[row.cls, { selected: row.activity.task_id === selectedTaskId }]"
                :style="{ left: row.x + 'px', width: row.w + 'px' }"
                :title="barTitle(row.activity)"
                @click="selectActivity(row.activity)"
              >
                <div class="g-bar-progress" :style="{ width: row.activity.pct_complete + '%' }"></div>
              </div>
            </template>
            <button
              v-if="row.type === 'activity' && annotations[row.activity.task_id]"
              class="g-note-dot annotation-hit"
              :style="{ left: (calloutAnchorX(row) + 3) + 'px' }"
              :title="(annotations[row.activity.task_id].callout ? 'Hide' : 'Show') + ' note: ' + annotations[row.activity.task_id].note"
              @mousedown.stop
              @click.stop="toggleCallout(row.activity.task_id)"
            ><i class="annotation-flag" :class="'sev-' + annotations[row.activity.task_id].severity"></i></button>
          </div>
        </template>

        <!-- Note callouts: opened from a note dot, dragged to wherever they read best.
             Only rows on this page carry one, so a callout prints on its bar's sheet. -->
        <div
          v-for="c in calloutsOf(pg)"
          :key="'co' + c.id"
          class="g-callout"
          :class="'sev-' + c.severity"
          :style="{ left: (labelColWidth + c.ax + c.dx) + 'px', top: (HEADER_HEIGHT + c.ay + c.dy - pg.start * ROW_HEIGHT) + 'px' }"
          title="Drag to move"
          @mousedown.stop="onCalloutDragStart($event, c)"
        >
          <div class="g-callout-head">
            <span class="g-callout-code">{{ c.code }}</span>
            <span v-if="c.severity" class="g-callout-sev">{{ severityLabel(c.severity) }}</span>
            <button class="g-callout-x" title="Hide note" @mousedown.stop @click.stop="toggleCallout(c.id)">&times;</button>
          </div>
          <div class="g-callout-text">{{ c.note }}</div>
        </div>
      </div>
      </template>
    </div>


    <ActivityDetailDrawer
      :activity="selectedActivity"
      :lookup="actLookup"
      :annotations="annotations"
      :project-name="data.project.proj_short_name"
      @close="selectedTaskId = null"
      @select="revealAndSelect"
      @annotate="(id, patch) => $emit('annotate', id, patch)"
      @unannotate="id => $emit('unannotate', id)"
    >
      <template #actions>
        <div class="detail-actions">
          <button v-if="!isolationActive" class="btn-tiny-light btn-isolate" @click="isolateSelected" title="Clear the chart down to just this activity, then click predecessors/successors below to rebuild its chain link by link">
            Isolate &amp; trace chain
          </button>
          <span v-else class="trace-hint">Tracing — click a predecessor or successor below to add it and walk the chain.</span>
        </div>
      </template>
    </ActivityDetailDrawer>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { Activity, Schedule, WbsNode } from '../types/schedule'
import { matchesNoteFilter, NOTE_FILTER_LABELS, DEFAULT_CALLOUT, SEVERITY_LABELS, type Annotations, type CalloutOffset, type NoteFilter, type Severity } from '../utils/annotations'
import { formatDate, formatDateShort, formatHours, isMilestone, formatFloat, formatLag, statusLabel } from '../utils/format'

const NEAR_CRITICAL_HRS = 80 // 10 working days
const FLOAT_TAIL_MAX_DAYS = 26
const STATUS_LABELS: Record<string, string> = { TK_NotStart: 'Not started', TK_Active: 'Active', TK_Complete: 'Complete' }
import fullscreenMixin from '../mixins/fullscreen'
import { relTypeLabel, cstrLabel, displayStart, displayEnd, CSTR_LABELS, CONSTRAINT_FILTER_GROUPS, constraintTypesOf, matchesConstraintFilter, constraintFilterLabel } from '../utils/p6'
import { dateSlipDays, finishSlipDays } from '../utils/compareChecks'
import { PAPER_SIZES, paperOrDefault, usableWidthPx, usableHeightPx } from '../utils/paper'
import {
  type Zoom,
  timelineRange, unionRange, dayWidthFor, clampDayWidth, totalWidth,
  dateToX, yearTicks, monthTicks, monthBandTicks, weekTicks, dayTicks, weekendRects,
  rowsPerPrintPage, printPageRanges, zoomForDayWidth,
  type Tick,
} from '../utils/ganttGeometry'
import IconChevron from './IconChevron.vue'
import ActivityDetailDrawer from './ActivityDetailDrawer.vue'

const LABEL_COL_WIDTH_DEFAULT = 428
const LABEL_COL_MIN = 200
// Long activity names need room; the cap leaves a fifth of the window for the bars.
const labelColMax = () => Math.max(700, Math.floor(window.innerWidth * 0.8))
const HEADER_HEIGHT = 56
const ROW_HEIGHT = 26
// 15px safety buffer: tuned against this chart's printed output (see utils/paper.ts).
const PRINT_BUFFER_PX = 15
// The title line above each printed sheet's grid: its height plus margin (see .print-title).
const PRINT_TITLE_HEIGHT = 24
function paperUsableWidthPx(key: string): number {
  return usableWidthPx(key, PRINT_BUFFER_PX)
}
const VIEW_STORAGE_KEY = 'schedule-app:gantt-view'

type CriticalBasis = 'tf0' | 'longest'
type LinksScope = 'critical' | 'all'

/** View settings persisted to localStorage. */
interface SavedView {
  zoom?: Zoom
  criticalBasis?: CriticalBasis
  showLinks?: boolean
  linksScope?: LinksScope
  showProgressLine?: boolean
  labelColWidth?: number
  dayWidthOverride?: number | null
  printPaperSize?: string
}

/** WBS ids, plus the synthetic group holding activities with no known WBS. */
type WbsKey = number | '__unassigned'

interface GridPage {
  screen: boolean
  /** Index of the page's first row in `rows`. */
  start: number
  rows: Row[]
  bodyHeight: number
  /** Where the frozen header and label column sit (the scroll offsets on screen). */
  top: number
  left: number
}

interface SlipCell { text: string; cls: string; title: string }
const NO_SLIP: SlipCell = { text: '', cls: '', title: '' }
function slipCellOf(d: number, was: string, what: string): SlipCell {
  return {
    text: (d > 0 ? '+' : '') + d + 'd',
    cls: d > 0 ? 'slip-late' : d < 0 ? 'slip-early' : '',
    title: d === 0 ? `${what} unchanged (${was})` : `${what} ${d > 0 ? 'later' : 'earlier'} by ${Math.abs(d)} calendar day${Math.abs(d) === 1 ? '' : 's'} (was ${was})`,
  }
}

// baseFinish: the latest compared finish of the activities under the node that the
// compared schedule also has (null without a compared schedule or with none in common).
interface Rollup { start: Date | null; finish: Date | null; baseFinish: Date | null; count: number }

interface WbsRow {
  type: 'wbs'
  key: string
  wbsId: WbsKey
  level: number
  name: string
  count: number
  start?: Date | null
  finish?: Date | null
  baseFinish?: Date | null
  index: number
}

interface ActivityRow {
  type: 'activity'
  key: string
  level: number
  activity: Activity
  milestone: boolean
  x: number
  w: number
  tailW: number
  cls: string
  index: number
}

type Row = WbsRow | ActivityRow

interface Callout {
  id: number
  code: string
  note: string
  severity: Severity | null
  /** The bar's finish end, in timeline coordinates (row centre). */
  ax: number
  ay: number
  dx: number
  dy: number
}
// Rows before `rows` numbers them.
type UnindexedRow = Omit<WbsRow, 'index'> | Omit<ActivityRow, 'index'>

/** Drag bookkeeping kept off the reactive state (Vue does not proxy `_`-prefixed data). */
interface DragState {
  _onDocMousedown: (e: MouseEvent) => void
  _panStartX: number
  _panStartY: number
  _panScrollLeft: number
  _panScrollTop: number
  _resizeStartX: number
  _resizeStartWidth: number
}
function drag(vm: object): DragState {
  return vm as DragState
}

function loadSavedView(): SavedView {
  try {
    const raw = localStorage.getItem(VIEW_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveView(view: SavedView): void {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(view))
  } catch {
    // localStorage unavailable (private browsing, quota) — view just won't persist.
  }
}

export default defineComponent({
  name: 'GanttChart',
  mixins: [fullscreenMixin],
  components: { IconChevron, ActivityDetailDrawer },
  props: {
    data: { type: Object as PropType<Schedule>, required: true },
    // A task id. Activities are keyed by number; a string id would silently match nothing.
    jumpTo: { type: Number as PropType<number | null>, default: null },
    annotations: { type: Object as PropType<Annotations>, default: () => ({}) },
    returnTab: { type: String, default: '' },
    // Parsed baseline schedule (from the Compare tab's snapshot/upload). When present,
    // activities matched by code can draw a ghost bar at their baseline position.
    baseline: { type: Object as PropType<Schedule | null>, default: null },
    // Its file name, for the printout's title line.
    baselineFilename: { type: String, default: '' },
  },
  emits: ['jumped', 'annotate', 'unannotate', 'return-to-origin', 'callout'],
  data() {
    const saved = loadSavedView()

    const start = this.data.project.earliest_start ? new Date(this.data.project.earliest_start) : new Date()
    const end = this.data.project.latest_end ? new Date(this.data.project.latest_end) : new Date()
    const days = Math.max(1, (end.getTime() - start.getTime()) / 86400000)
    const autoZoom: Zoom = days > 300 ? 'month' : days > 100 ? 'week' : 'day'

    const expandedWbs = new Set<WbsKey>()
    const markExpanded = (node: WbsNode, level: number) => {
      if (level < 1) expandedWbs.add(node.wbs_id)
      for (const c of node.children || []) markExpanded(c, level + 1)
    }
    for (const root of this.data.wbs_tree || []) markExpanded(root, 0)

    return {
      HEADER_HEIGHT,
      ROW_HEIGHT,
      zoom: saved.zoom || autoZoom,
      zoomLevels: ['day', 'week', 'month', 'quarter'] as Zoom[],
      printPaperSize: saved.printPaperSize || 'a4',
      paperSizes: PAPER_SIZES,
      dayWidthOverride: saved.dayWidthOverride ?? null,
      labelColWidth: Math.min(saved.labelColWidth || LABEL_COL_WIDTH_DEFAULT, labelColMax()),
      criticalBasis: (saved.criticalBasis || 'tf0') as CriticalBasis,
      expandedWbs,
      // WBS ids collapsed while a filter is active. Filtering auto-expands everything so
      // matches are revealed, but a collapse click during filtering must still stick —
      // this set records those, and clears when filters clear.
      filterCollapsed: new Set<WbsKey>(),
      showBaseline: true,
      // True between Print and the end of printing: the grid is drawn as sheets (gridPages).
      printing: false,
      showLinks: saved.showLinks ?? true,
      linksScope: (saved.linksScope || 'critical') as LinksScope,
      showProgressLine: saved.showProgressLine ?? false,
      selectedTaskId: null as number | null,
      filterText: '',
      filterStatus: '',
      filterCriticalOnly: false,
      filterConstraint: '',
      filterNotes: '' as NoteFilter,
      filterFrom: '',
      filterTo: '',
      overflowOpen: false,
      filterCodes: Object.fromEntries<string>((this.data.project.activity_code_types || []).map(t => [t, ''])),
      // Chain tracing: null = off; a Set of task_ids = show ONLY these activities.
      // Grown one activity at a time by clicking predecessors/successors in the drawer,
      // letting a reviewer reconstruct a driving chain link by link.
      isolatedIds: null as Set<number> | null,
      scrollLeftPx: 0,
      scrollTopPx: 0,
      panning: false,
      resizing: false,
      // The callout being dragged, with its offset live until the drop saves it.
      calloutDrag: null as { id: number; startX: number; startY: number; dx0: number; dy0: number; dx: number; dy: number } | null,
    }
  },
  mounted() {
    window.addEventListener('keydown', this.onKeydown)
    // The drawer is a fixed overlay; a click on app chrome outside this component
    // (tab bar, summary toggle, another tab's controls) dismisses it instead of the
    // overlay swallowing the interaction context.
    drag(this)._onDocMousedown = (e: MouseEvent) => {
      const target = e.target as Element
      if (this.overflowOpen && !target.closest('.tb-pop')) {
        this.overflowOpen = false
      }
      if (this.selectedTaskId && this.$el.offsetParent !== null && !this.$el.contains(target)) {
        this.selectedTaskId = null
      }
    }
    document.addEventListener('mousedown', drag(this)._onDocMousedown)
  },
  beforeUnmount() {
    document.removeEventListener('mousedown', drag(this)._onDocMousedown)
    window.removeEventListener('keydown', this.onKeydown)
    window.removeEventListener('mousemove', this.onPanMove)
    window.removeEventListener('mouseup', this.onPanEnd)
    window.removeEventListener('mousemove', this.onResizeMove)
    window.removeEventListener('mouseup', this.onResizeEnd)
    window.removeEventListener('mousemove', this.onCalloutDragMove)
    window.removeEventListener('mouseup', this.onCalloutDragEnd)
  },
  watch: {
    // The component survives file swaps (tabs use v-show), so reseed the per-category
    // filter keys for the new file — an undefined v-model renders the select blank.
    data() {
      this.clearFilters()
    },
    zoom() { this.persistView() },
    criticalBasis() { this.persistView() },
    showLinks() { this.persistView() },
    linksScope() { this.persistView() },
    showProgressLine() { this.persistView() },
    dayWidthOverride() { this.persistView() },
    jumpTo: {
      immediate: true,
      handler(taskId: number | null) {
        if (taskId == null) return
        this.revealAndSelect(taskId)
        this.$emit('jumped')
      },
    },
  },
  computed: {
    actLookup(): Map<number, Activity> {
      const m = new Map<number, Activity>()
      for (const a of this.data.activities) m.set(a.task_id, a)
      return m
    },
    selectedActivity(): Activity | null | undefined {
      return this.selectedTaskId != null ? this.actLookup.get(this.selectedTaskId) : null
    },
    wbsParentOf(): Map<number, number> {
      const map = new Map<number, number>()
      const walk = (node: WbsNode, parentId: number | null) => {
        if (parentId != null) map.set(node.wbs_id, parentId)
        for (const c of node.children || []) walk(c, node.wbs_id)
      }
      for (const root of this.data.wbs_tree || []) walk(root, null)
      return map
    },
    activitiesByWbs(): Map<number, Activity[]> {
      const map = new Map<number, Activity[]>()
      for (const a of this.data.activities) {
        if (!map.has(a.wbs_id)) map.set(a.wbs_id, [])
        map.get(a.wbs_id)!.push(a)
      }
      for (const list of map.values()) {
        list.sort((a, b) => {
          const da = displayStart(a) || ''
          const db = displayStart(b) || ''
          if (da !== db) return da < db ? -1 : 1
          return a.task_code < b.task_code ? -1 : a.task_code > b.task_code ? 1 : 0
        })
      }
      return map
    },
    rollups(): Map<number, Rollup> {
      return this.computeRollups(null)
    },
    rollupsFiltered(): Map<number, Rollup> | null {
      const matched = this.matchedTaskIds
      return matched ? this.computeRollups(a => matched.has(a.task_id)) : null
    },
    activeRollups(): Map<number, Rollup> {
      return this.isFilterActive && this.rollupsFiltered ? this.rollupsFiltered : this.rollups
    },
    // Spans both schedules when baseline ghosts are visible, so a baseline that runs
    // past the current programme still lands inside the drawn grid.
    timelineBounds(): { rangeStart: Date; rangeEnd: Date } {
      const p = this.data.project
      let { start, end } = { start: p.earliest_start, end: p.latest_end }
      if (this.baseline && this.showBaseline) {
        const b = this.baseline.project
        ;({ start, end } = unionRange(start, end, b.earliest_start, b.latest_end))
      }
      return timelineRange(start, end)
    },
    rangeStart(): Date {
      return this.timelineBounds.rangeStart
    },
    rangeEnd(): Date {
      return this.timelineBounds.rangeEnd
    },
    dayWidth(): number {
      return dayWidthFor(this.zoom, this.dayWidthOverride)
    },
    totalWidth(): number {
      return totalWidth(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    bodyHeight(): number {
      return this.rows.length * ROW_HEIGHT
    },
    // The pages the grid is drawn as. On screen: one page with every row, its header and
    // label column following the scroll position.
    // While printing: one page per sheet, each with as many rows as fit below the
    // sheet's title line and the repeated column header.
    gridPages(): GridPage[] {
      if (!this.printing) {
        return [{ screen: true, start: 0, rows: this.rows, bodyHeight: this.bodyHeight, top: this.scrollTopPx, left: this.scrollLeftPx }]
      }
      const perPage = rowsPerPrintPage(usableHeightPx(this.printPaperSize, PRINT_BUFFER_PX), PRINT_TITLE_HEIGHT + HEADER_HEIGHT, ROW_HEIGHT)
      return printPageRanges(this.rows.length, perPage).map(({ start, end }) => ({
        screen: false, start, rows: this.rows.slice(start, end), bodyHeight: (end - start) * ROW_HEIGHT, top: 0, left: 0,
      }))
    },
    yearTicks(): Tick[] {
      return yearTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    // Months read as the band at day/week zoom; at month/quarter zoom the months are
    // already the ticks, so the band steps up to years.
    // The zoom the header ticks follow: the chosen one on screen; on a printed sheet,
    // whose day width is fitted to the paper, the one that suits that width.
    tickZoom(): Zoom {
      return this.printing ? zoomForDayWidth(this.dayWidth) : this.zoom
    },
    bandTicks(): Tick[] {
      return this.tickZoom === 'day' || this.tickZoom === 'week'
        ? monthBandTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
        : yearTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    monthTicks(): Tick[] {
      return monthTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    weekTicks(): Tick[] {
      return weekTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    dayTicks(): Tick[] {
      return dayTicks(this.rangeStart, this.rangeEnd, this.dayWidth)
    },
    detailTicks(): Tick[] {
      if (this.tickZoom === 'month' || this.tickZoom === 'quarter') return this.monthTicks
      if (this.tickZoom === 'week') return this.weekTicks
      return this.dayTicks
    },
    secondaryMonthGridlines(): Tick[] {
      return this.tickZoom === 'day' || this.tickZoom === 'week' ? this.monthTicks : []
    },
    weekendRects(): { x: number; w: number }[] {
      if (this.tickZoom !== 'day') return []
      return weekendRects(this.dayTicks, this.dayWidth)
    },
    todayX(): number | null {
      const today = new Date()
      if (today < this.rangeStart || today > this.rangeEnd) return null
      return Math.round(((today.getTime() - this.rangeStart.getTime()) / 86400000) * this.dayWidth)
    },
    dataDateX(): number | null {
      if (!this.data.project.data_date) return null
      const dd = new Date(this.data.project.data_date)
      if (isNaN(dd.getTime()) || dd < this.rangeStart || dd > this.rangeEnd) return null
      const x = Math.round(((dd.getTime() - this.rangeStart.getTime()) / 86400000) * this.dayWidth)
      // When the file is fresh, data date ≈ today — don't stack two flags on one pixel.
      return this.todayX !== null && Math.abs(x - this.todayX) < 3 ? null : x
    },
    // Print has no "Today" marker at all (today's date isn't meaningful once printed
    // and later read), so the data date always shows, unlike the on-screen version.
    printDataDateX(): number | null {
      if (!this.data.project.data_date) return null
      const dd = new Date(this.data.project.data_date)
      if (isNaN(dd.getTime()) || dd < this.rangeStart || dd > this.rangeEnd) return null
      return Math.round(((dd.getTime() - this.rangeStart.getTime()) / 86400000) * this.dayWidth)
    },
    codeTypesAvailable(): string[] {
      return this.data.project.has_activity_codes ? this.data.project.activity_code_types : []
    },
    codeValuesByType(): Map<string, string[]> {
      const sets = new Map<string, Set<string>>()
      for (const t of this.codeTypesAvailable) sets.set(t, new Set())
      for (const a of this.data.activities) {
        for (const c of a.activity_codes) {
          sets.get(c.type)?.add(c.code)
        }
      }
      const m = new Map<string, string[]>()
      for (const [t, set] of sets) m.set(t, [...set].sort())
      return m
    },
    // The groups first, then each P6 type in its usual order, counted on this file so an
    // empty choice is visibly empty rather than a surprise blank chart.
    constraintFilterOptions(): { value: string; label: string; count: number }[] {
      const counts = new Map<string, number>()
      const bump = (k: string) => counts.set(k, (counts.get(k) || 0) + 1)
      for (const a of this.data.activities) {
        const types = constraintTypesOf(a)
        for (const t of new Set(types)) bump(t)
        for (const g of Object.keys(CONSTRAINT_FILTER_GROUPS)) if (matchesConstraintFilter(a, g)) bump(g)
      }
      const groups = Object.entries(CONSTRAINT_FILTER_GROUPS).map(([value, label]) => ({ value, label, count: counts.get(value) || 0 }))
      const types = Object.keys(CSTR_LABELS).filter(t => counts.has(t))
        .map(t => ({ value: t, label: cstrLabel(t), count: counts.get(t)! }))
      return [...groups, ...types]
    },
    // Counted over this file's activities, so a note left on an activity the file no
    // longer has doesn't promise a match.
    noteFilterOptions(): { value: NoteFilter; label: string; count: number }[] {
      const notes = this.data.activities.map(a => this.annotations[a.task_id]).filter(Boolean)
      return (Object.entries(NOTE_FILTER_LABELS) as [NoteFilter, string][])
        .map(([value, label]) => ({ value, label, count: notes.filter(n => matchesNoteFilter(n, value)).length }))
    },
    activeCodeFilters(): [string, string][] {
      return Object.entries(this.filterCodes).filter(([, v]) => v)
    },
    isolationActive(): boolean {
      return this.isolatedIds !== null
    },
    isFilterActive(): boolean {
      return this.isolationActive || !!(this.filterText.trim() || this.filterStatus || this.filterConstraint || this.filterNotes || this.filterCriticalOnly || this.filterFrom || this.filterTo || this.activeCodeFilters.length)
    },
    matchedTaskIds(): Set<number> | null {
      // Isolation takes precedence over the text/status/code filters: the trace IS the view.
      if (this.isolatedIds) return this.isolatedIds
      if (!this.isFilterActive) return null
      const q = this.filterText.trim().toLowerCase()
      const ids = new Set<number>()
      for (const a of this.data.activities) {
        if (q && !(a.task_code.toLowerCase().includes(q) || a.task_name.toLowerCase().includes(q) || (a.wbs_path && a.wbs_path.toLowerCase().includes(q)))) continue
        if (this.filterStatus && a.status !== this.filterStatus) continue
        if (this.filterFrom || this.filterTo) {
          // Window-intersection on the display dates (actual once started, else early):
          // an activity is shown if any part of it touches [from, to]. ISO date-prefix
          // string comparison is deliberate — no timezone surprises.
          const aStart = (displayStart(a) || '').slice(0, 10)
          const aEnd = (displayEnd(a) || aStart || '').slice(0, 10)
          if (!aStart) continue
          if (this.filterFrom && aEnd < this.filterFrom) continue
          if (this.filterTo && aStart > this.filterTo) continue
        }
        if (!matchesConstraintFilter(a, this.filterConstraint)) continue
        if (!matchesNoteFilter(this.annotations[a.task_id], this.filterNotes)) continue
        if (this.filterCriticalOnly && !this.isBasisCritical(a)) continue
        if (this.activeCodeFilters.length) {
          const matchesAll = this.activeCodeFilters.every(([type, code]) =>
            a.activity_codes.some(c => c.type === type && c.code === code)
          )
          if (!matchesAll) continue
        }
        ids.add(a.task_id)
      }
      return ids
    },
    // The slip column belongs to the two-schedule view: it shows whenever the compared
    // schedule's bars are drawn beside the current ones.
    showSlip(): boolean {
      return !!this.baseline && this.showBaseline
    },
    baselineByCode(): Map<string, Activity> | null {
      if (!this.baseline) return null
      const m = new Map<string, Activity>()
      for (const a of this.baseline.activities) m.set(a.task_code, a)
      return m
    },
    // One removable chip per active filter — the strip states exactly what is
    // narrowing the view, so a filtered chart can't be read as the whole programme.
    activeFilterChips(): { id: string; label: string }[] {
      const out: { id: string; label: string }[] = []
      const q = this.filterText.trim()
      if (q) out.push({ id: 'text', label: `Search: ${q}` })
      if (this.filterStatus) out.push({ id: 'status', label: `Status: ${STATUS_LABELS[this.filterStatus] || this.filterStatus}` })
      if (this.filterConstraint) out.push({ id: 'cstr', label: `Constraint: ${constraintFilterLabel(this.filterConstraint)}` })
      if (this.filterNotes) out.push({ id: 'notes', label: `Notes: ${NOTE_FILTER_LABELS[this.filterNotes]}` })
      if (this.filterCriticalOnly) out.push({ id: 'crit', label: 'Critical only' })
      if (this.filterFrom || this.filterTo) {
        const la = [28, 56].find(d => this.lookAheadActive(d))
        out.push({ id: 'dates', label: la
          ? `${la / 7}-week look-ahead`
          : `Window: ${this.filterFrom ? formatDateShort(this.filterFrom) : '…'} – ${this.filterTo ? formatDateShort(this.filterTo) : '…'}` })
      }
      for (const [type, code] of this.activeCodeFilters) out.push({ id: 'code:' + type, label: `${type}: ${code}` })
      return out
    },
    emptyFilterHint(): string {
      const bits: string[] = []
      if (this.filterText.trim()) bits.push(`text “${this.filterText.trim()}”`)
      if (this.filterStatus) bits.push('a status')
      if (this.filterConstraint) bits.push('a constraint')
      if (this.filterNotes) bits.push('notes')
      if (this.filterCriticalOnly) bits.push('critical only')
      if (this.filterFrom || this.filterTo) bits.push('a date window')
      if (this.activeCodeFilters.length) bits.push('an activity code')
      return bits.length
        ? `Filtering by ${bits.join(', ')}.`
        : 'This schedule has no activities to show.'
    },
    matchCount(): number {
      return this.matchedTaskIds ? this.matchedTaskIds.size : this.data.activities.length
    },
    rows(): Row[] {
      const rows: UnindexedRow[] = []
      const filtering = this.isFilterActive
      // Non-null whenever `filtering` is true: an active filter always yields a match set.
      const matched = this.matchedTaskIds as Set<number>
      const rollups = this.activeRollups
      const walk = (nodes: WbsNode[], level: number) => {
        const sorted = [...nodes].sort((a, b) => a.seq_num - b.seq_num)
        for (const node of sorted) {
          const roll = rollups.get(node.wbs_id) || { start: null, finish: null, baseFinish: null, count: 0 }
          if (filtering && roll.count === 0) continue
          rows.push({
            type: 'wbs',
            key: 'w' + node.wbs_id,
            wbsId: node.wbs_id,
            level,
            name: node.wbs_short_name ? `${node.wbs_short_name} ${node.wbs_name}` : node.wbs_name,
            count: roll.count,
            start: roll.start,
            finish: roll.finish,
            baseFinish: roll.baseFinish,
          })
          const expanded = filtering ? !this.filterCollapsed.has(node.wbs_id) : this.expandedWbs.has(node.wbs_id)
          if (expanded) {
            walk(node.children || [], level + 1)
            for (const a of this.activitiesByWbs.get(node.wbs_id) || []) {
              if (filtering && !matched.has(a.task_id)) continue
              rows.push(this.buildActivityRow(a, level + 1))
            }
          }
        }
      }
      walk(this.data.wbs_tree || [], 0)

      const orphansAll = this.data.activities.filter(a => !this.allWbsIds.has(a.wbs_id))
      const orphans = filtering ? orphansAll.filter(a => matched.has(a.task_id)) : orphansAll
      if (orphans.length) {
        rows.push({ type: 'wbs', key: 'w-unassigned', wbsId: '__unassigned', level: 0, name: '(Unassigned)', count: orphans.length })
        if (filtering ? !this.filterCollapsed.has('__unassigned') : this.expandedWbs.has('__unassigned')) {
          for (const a of orphans) rows.push(this.buildActivityRow(a, 1))
        }
      }

      rows.forEach((r, i) => { (r as Row).index = i })
      return rows as Row[]
    },
    allWbsIds(): Set<number> {
      const ids = new Set<number>()
      const walk = (nodes: WbsNode[]) => {
        for (const n of nodes) { ids.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      return ids
    },
    rowIndexByTaskId(): Map<number, number> {
      const map = new Map<number, number>()
      this.rows.forEach(r => { if (r.type === 'activity') map.set(r.activity.task_id, r.index) })
      return map
    },
    links(): { id: string; d: string; chain: boolean }[] {
      // Chain tracing draws its links regardless of the Links toggle — they're the point.
      if (!this.showLinks && !this.isolationActive) return []
      const out: { id: string; d: string; chain: boolean }[] = []
      const rowByIndex = this.rows
      for (const row of rowByIndex) {
        if (row.type !== 'activity') continue
        // Normal mode: "Critical only" scope draws just critical-to-critical links (per
        // the selected basis) to keep large schedules legible; "All logic" draws every
        // relationship. Isolation mode always draws every relationship between traced
        // activities, with non-critical ones styled as "chain" links.
        const criticalScope = !this.isolationActive && this.linksScope === 'critical'
        if (criticalScope && !this.isBasisCritical(row.activity)) continue
        for (const p of row.activity.predecessors || []) {
          const predIdx = this.rowIndexByTaskId.get(p.task_id)
          if (predIdx === undefined) continue
          const predRow = rowByIndex[predIdx] as ActivityRow // rowIndexByTaskId only indexes activity rows
          const bothCritical = this.isBasisCritical(row.activity) && this.isBasisCritical(predRow.activity)
          if (criticalScope && !bothCritical) continue
          const predX = this.dateToX(displayEnd(predRow.activity))
          const predY = predIdx * ROW_HEIGHT + ROW_HEIGHT / 2
          const succX = row.x
          const succY = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
          if (predX === null || succX === null) continue
          const midX = predX + 8
          out.push({
            id: `${p.task_id}-${row.activity.task_id}-${p.type}-${out.length}`,
            d: `M${predX},${predY} L${midX},${predY} L${midX},${succY} L${succX},${succY}`,
            chain: !bothCritical,
          })
        }
      }
      return out
    },
    progressLinePoints(): { x: number; y: number }[] {
      if (!this.showProgressLine) return []
      const pts: { x: number; y: number }[] = []
      for (const row of this.rows) {
        if (row.type !== 'activity' || row.milestone) continue
        const px = row.x + row.w * (row.activity.pct_complete / 100)
        const py = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
        pts.push({ x: px, y: py })
      }
      return pts
    },
    progressLinePath(): string {
      if (this.progressLinePoints.length < 2) return ''
      return 'M' + this.progressLinePoints.map(p => `${p.x},${p.y}`).join(' L')
    },
  },
  methods: {
    computeRollups(matchFn: ((a: Activity) => boolean) | null): Map<number, Rollup> {
      const map = new Map<number, Rollup>()
      const activitiesByWbs = this.activitiesByWbs
      const baselineByCode = this.baselineByCode
      const visit = (node: WbsNode): Rollup => {
        let start: Date | null = null, finish: Date | null = null, baseFinish: Date | null = null, count = 0
        for (const a of activitiesByWbs.get(node.wbs_id) || []) {
          if (matchFn && !matchFn(a)) continue
          count++
          const b = baselineByCode?.get(a.task_code)
          const be = b ? displayEnd(b) : null
          if (be) {
            const d = new Date(be)
            if (!baseFinish || d > baseFinish) baseFinish = d
          }
          const ds = displayStart(a)
          const de = displayEnd(a)
          if (ds) {
            const d = new Date(ds)
            if (!start || d < start) start = d
          }
          if (de) {
            const d = new Date(de)
            if (!finish || d > finish) finish = d
          }
        }
        for (const child of node.children || []) {
          const r = visit(child)
          count += r.count
          if (r.start && (!start || r.start < start)) start = r.start
          if (r.finish && (!finish || r.finish > finish)) finish = r.finish
          if (r.baseFinish && (!baseFinish || r.baseFinish > baseFinish)) baseFinish = r.baseFinish
        }
        const roll = { start, finish, baseFinish, count }
        map.set(node.wbs_id, roll)
        return roll
      }
      for (const root of this.data.wbs_tree || []) visit(root)
      return map
    },
    dateToX(dateStr: string | null | undefined): number | null {
      return dateToX(dateStr, this.rangeStart, this.dayWidth)
    },
    isBasisCritical(a: Activity): boolean {
      return this.criticalBasis === 'longest' ? a.is_longest_path : a.is_critical
    },
    // The number a reviewer reads most often, now in the grid rather than only in
    // the drawer — same severity bands as the bars.
    floatCellClass(a: Activity): string {
      if (a.total_float_hrs == null) return ''
      if (a.total_float_hrs < 0) return 'fl-neg'
      if (a.total_float_hrs === 0) return 'fl-crit'
      if (a.total_float_hrs <= NEAR_CRITICAL_HRS) return 'fl-near'
      return ''
    },
    classifyActivity(a: Activity): string {
      const base = this.isBasisCritical(a)
        ? 'critical'
        : (this.criticalBasis === 'tf0' && a.total_float_hrs != null && a.total_float_hrs > 0 && a.total_float_hrs <= 80 ? 'near' : 'other')
      // Negative float means the activity is already behind an imposed date — flag it
      // regardless of critical basis, since that's a property of the activity itself.
      return a.is_negative_float ? `${base} negative` : base
    },
    buildActivityRow(a: Activity, level: number): Omit<ActivityRow, 'index'> {
      const milestone = isMilestone(a)
      const x = this.dateToX(displayStart(a))
      const xEnd = this.dateToX(displayEnd(a))
      const w = milestone ? 0 : Math.max((xEnd ?? x ?? 0) - (x ?? 0), 3)
      // Slack drawn as a dashed tail off the bar end: float becomes something you see
      // in the chart, not a number to look up. Capped so a 200-day tail can't dominate.
      const tfDays = a.total_float_hrs != null ? a.total_float_hrs / (a.calendar_hrs_per_day || 8) : 0
      const tailW = tfDays > 0 && tfDays <= FLOAT_TAIL_MAX_DAYS ? Math.round(tfDays * this.dayWidth) : 0
      return {
        type: 'activity' as const, key: 'a' + a.task_id, level, activity: a,
        milestone, x: x ?? 0, w, tailW, cls: this.classifyActivity(a),
      }
    },
    wbsBarStyle(row: WbsRow): Record<string, string> {
      if (!row.start || !row.finish) return { display: 'none' }
      const x = this.dateToX(row.start.toISOString())
      const xEnd = this.dateToX(row.finish.toISOString())
      // `?? 0` mirrors JS's null-to-0 coercion in subtraction.
      return { left: x + 'px', width: Math.max((xEnd ?? 0) - (x ?? 0), 3) + 'px' }
    },
    // The data-date line's position: on screen it yields to a nearby Today line; a printed
    // sheet has no Today line, so it always shows.
    ddX(pg: GridPage): number | null {
      return pg.screen ? this.dataDateX : this.printDataDateX
    },
    slipCell(a: Activity): SlipCell {
      const b = this.baselineByCode?.get(a.task_code)
      if (!b) return { text: 'new', cls: 'slip-new', title: 'Not in the compared schedule' }
      const d = finishSlipDays(a, b)
      return d === null ? NO_SLIP : slipCellOf(d, formatDateShort(displayEnd(b)), 'Finish')
    },
    // A WBS row's finish is the latest finish under it, as shown in its Finish cell; it is
    // measured against the latest compared finish of the same activities.
    wbsSlipCell(row: WbsRow): SlipCell {
      if (!row.finish) return NO_SLIP
      if (!row.baseFinish) return { text: 'new', cls: 'slip-new', title: 'None of these activities is in the compared schedule' }
      return slipCellOf(dateSlipDays(row.finish, row.baseFinish), formatDateShort(row.baseFinish.toISOString()), 'Latest finish')
    },
    ghostFor(a: Activity): { x: number | null; w: number; label: string } | null {
      if (!this.showBaseline || !this.baselineByCode) return null
      const b = this.baselineByCode.get(a.task_code)
      if (!b) return null
      const s = displayStart(b)
      const e = displayEnd(b)
      if (!s) return null
      const x = this.dateToX(s)
      const xEnd = e ? this.dateToX(e) : x
      return {
        x,
        w: Math.max((xEnd ?? 0) - (x ?? 0), 3), // `?? 0` mirrors JS's null-to-0 coercion
        label: `${formatDateShort(s)}${e && e !== s ? ' → ' + formatDateShort(e) : ''}`,
      }
    },
    toggleWbs(wbsId: WbsKey) {
      if (this.isFilterActive) {
        if (this.filterCollapsed.has(wbsId)) this.filterCollapsed.delete(wbsId)
        else this.filterCollapsed.add(wbsId)
        // Force reactivity: Set mutations aren't tracked by Vue 3 unless reassigned.
        this.filterCollapsed = new Set(this.filterCollapsed)
        return
      }
      if (this.expandedWbs.has(wbsId)) this.expandedWbs.delete(wbsId)
      else this.expandedWbs.add(wbsId)
      this.expandedWbs = new Set(this.expandedWbs)
    },
    allWbsIdSet(): Set<WbsKey> {
      const all = new Set<WbsKey>()
      const walk = (nodes: WbsNode[]) => {
        for (const n of nodes) { all.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      all.add('__unassigned')
      return all
    },
    expandAll() {
      if (this.isFilterActive) {
        this.filterCollapsed = new Set()
        return
      }
      this.expandedWbs = this.allWbsIdSet()
    },
    wbsNodesByLevel(): { id: number; level: number }[] {
      const out: { id: number; level: number }[] = []
      const walk = (nodes: WbsNode[], level: number) => {
        for (const n of nodes) { out.push({ id: n.wbs_id, level }); walk(n.children || [], level + 1) }
      }
      walk(this.data.wbs_tree || [], 0)
      return out
    },
    _wbsExpanded(id: WbsKey): boolean {
      return this.isFilterActive ? !this.filterCollapsed.has(id) : this.expandedWbs.has(id)
    },
    _setWbsExpanded(ids: WbsKey[], expand: boolean) {
      if (this.isFilterActive) {
        const set = new Set(this.filterCollapsed)
        ids.forEach(id => (expand ? set.delete(id) : set.add(id)))
        this.filterCollapsed = set
      } else {
        const set = new Set(this.expandedWbs)
        ids.forEach(id => (expand ? set.add(id) : set.delete(id)))
        this.expandedWbs = set
      }
    },
    // One level at a time: expand the shallowest collapsed ring / collapse the deepest
    // expanded one — stepping through the hierarchy the way P6's outline levels do.
    expandOneLevel() {
      const collapsed = this.wbsNodesByLevel().filter(n => !this._wbsExpanded(n.id))
      if (!collapsed.length) return
      const lvl = Math.min(...collapsed.map(n => n.level))
      this._setWbsExpanded(collapsed.filter(n => n.level === lvl).map(n => n.id), true)
    },
    collapseOneLevel() {
      const expanded = this.wbsNodesByLevel().filter(n => this._wbsExpanded(n.id))
      if (!expanded.length) return
      const lvl = Math.max(...expanded.map(n => n.level))
      this._setWbsExpanded(expanded.filter(n => n.level === lvl).map(n => n.id), false)
    },
    collapseAll() {
      if (this.isFilterActive) {
        this.filterCollapsed = this.allWbsIdSet()
        return
      }
      this.expandedWbs = new Set()
    },
    selectActivity(a: Activity) {
      const wasSelected = this.selectedTaskId === a.task_id
      this.selectedTaskId = wasSelected ? null : a.task_id
      if (!wasSelected) {
        this.$nextTick(() => this.scrollToActivity(a.task_id))
      }
    },
    // Defers a scrollTo past two animation frames. Chromium can leave
    // position:sticky elements mis-computed if scrollLeft/scrollTop are set
    // right alongside a reactive DOM mutation (e.g. the .selected class toggle
    // that triggers this scroll) — two rAFs guarantee a real layout+paint has
    // settled first. Cheap enough that it's used for every programmatic scroll.
    deferredScrollTo(el: HTMLElement, opts: ScrollToOptions) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.scrollTo(opts)
        })
      })
    },
    scrollToActivity(taskId: number | null) {
      const idx = taskId == null ? undefined : this.rowIndexByTaskId.get(taskId)
      const el = this.$refs.scrollEl as HTMLElement | undefined
      if (idx === undefined || !el) return
      const row = this.rows[idx]
      const top = Math.max(0, idx * ROW_HEIGHT - el.clientHeight / 2)
      let left = el.scrollLeft
      if (row && row.type === 'activity') {
        left = Math.max(0, row.x - el.clientWidth / 2 + this.labelColWidth)
      }
      this.deferredScrollTo(el, { top, left, behavior: 'smooth' })
    },
    onKeydown(e: KeyboardEvent) {
      // Only when this tab is actually on screen (tabs stay mounted via v-show).
      if (!this.$el || this.$el.offsetParent === null) return
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '')
      if (e.key === 'Escape') {
        if (this.selectedTaskId != null) { this.selectedTaskId = null; return }
        if (this.isolationActive) this.exitIsolation()
      } else if (e.key === '/' && !typing) {
        e.preventDefault()
        this.$el.querySelector('.filter-input')?.focus()
      } else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !typing) {
        e.preventDefault()
        this.moveSelection(e.key === 'ArrowDown' ? 1 : -1)
      }
    },
    // ↑/↓ walk the visible activity rows (skipping WBS headers); the drawer follows.
    moveSelection(dir: number) {
      const actRows = this.rows.filter((r): r is ActivityRow => r.type === 'activity')
      if (!actRows.length) return
      let idx = actRows.findIndex(r => r.activity.task_id === this.selectedTaskId)
      idx = idx === -1 ? (dir > 0 ? 0 : actRows.length - 1) : Math.min(actRows.length - 1, Math.max(0, idx + dir))
      const next = actRows[idx].activity
      if (next.task_id === this.selectedTaskId) return
      this.selectedTaskId = next.task_id
      this.$nextTick(() => this.scrollToActivity(next.task_id))
    },
    clearFilter(id: string) {
      if (id === 'text') this.filterText = ''
      else if (id === 'status') this.filterStatus = ''
      else if (id === 'cstr') this.filterConstraint = ''
      else if (id === 'notes') this.filterNotes = ''
      else if (id === 'crit') this.filterCriticalOnly = false
      else if (id === 'dates') { this.filterFrom = ''; this.filterTo = '' }
      else if (id.startsWith('code:')) this.filterCodes[id.slice(5)] = ''
    },
    // The code picker is a one-shot menu: a pick sets that category's filter (shown as a
    // chip beside it) and the menu returns to its prompt for the next pick.
    addCodeFilter(e: Event) {
      const sel = e.target as HTMLSelectElement
      if (sel.value) {
        const [type, code] = JSON.parse(sel.value) as [string, string]
        this.filterCodes[type] = code
      }
      sel.value = ''
    },
    clearFilters() {
      this.filterCollapsed = new Set()
      this.filterText = ''
      this.filterStatus = ''
      this.filterCriticalOnly = false
      this.filterConstraint = ''
      this.filterNotes = ''
      this.filterFrom = ''
      this.filterTo = ''
      // Reseed one '' entry per category — an undefined v-model renders the select blank.
      this.filterCodes = Object.fromEntries<string>((this.data.project.activity_code_types || []).map(t => [t, '']))
      this.isolatedIds = null
    },
    // Look-ahead: the window every site meeting asks for — data date + N days.
    lookAheadWindow(days: number): { from: string; to: string } | null {
      const dd = this.data.project.data_date
      if (!dd) return null
      const from = dd.slice(0, 10)
      const end = new Date(from + 'T12:00:00')
      end.setDate(end.getDate() + days)
      const to = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`
      return { from, to }
    },
    lookAheadActive(days: number): boolean {
      const w = this.lookAheadWindow(days)
      return !!w && this.filterFrom === w.from && this.filterTo === w.to
    },
    setLookAhead(days: number) {
      const w = this.lookAheadWindow(days)
      if (!w) return
      if (this.lookAheadActive(days)) {
        this.filterFrom = ''
        this.filterTo = ''
      } else {
        this.filterFrom = w.from
        this.filterTo = w.to
      }
    },
    isolateSelected() {
      if (this.selectedTaskId == null) return
      this.isolatedIds = new Set([this.selectedTaskId])
      this.$nextTick(() => this.scrollToActivity(this.selectedTaskId))
    },
    exitIsolation() {
      const keep = this.selectedTaskId
      this.isolatedIds = null
      // Re-reveal the activity we were parked on so the exit doesn't strand the
      // selection under a collapsed WBS branch.
      if (keep != null) this.revealAndSelect(keep)
    },
    scrollToToday() {
      const el = this.$refs.scrollEl as HTMLElement | undefined
      if (this.todayX === null || !el) return
      this.deferredScrollTo(el, { left: Math.max(0, this.todayX - el.clientWidth / 2), behavior: 'smooth' })
    },
    printGantt() {
      // Auto-fit width: rather than visually shrinking the rendered canvas (tried and
      // reverted — CSS transform doesn't reliably interact with this app's absolutely-
      // positioned rows/links under print pagination, see the print CSS comment below),
      // temporarily set an EXACT continuous day-width (the same dayWidthOverride
      // mechanism ctrl+scroll zoom already uses) so the timeline fills the selected
      // paper's usable width precisely — no clipping, no wasted margin, no new
      // rendering path to distrust.
      const days = Math.max(1, (this.rangeEnd.getTime() - this.rangeStart.getTime()) / 86400000)
      const target = paperUsableWidthPx(this.printPaperSize) - this.labelColWidth
      const fitDayWidth = clampDayWidth(target / days)
      const prevOverride = this.dayWidthOverride
      this.dayWidthOverride = fitDayWidth
      this.printing = true
      const pageCss = paperOrDefault(this.printPaperSize).pageCss
      const styleTag = document.createElement('style')
      styleTag.textContent = `@page { size: ${pageCss} landscape; margin: 10mm; }`
      document.head.appendChild(styleTag)
      const restore = () => {
        this.printing = false
        this.dayWidthOverride = prevOverride
        styleTag.remove()
      }
      window.addEventListener('afterprint', restore, { once: true })
      // Wait for Vue to re-render at the fitted width (and the browser to lay it out)
      // before the print dialog captures the page.
      this.$nextTick(() => requestAnimationFrame(() => window.print()))
    },
    persistView() {
      saveView({
        zoom: this.zoom,
        criticalBasis: this.criticalBasis,
        showLinks: this.showLinks,
        linksScope: this.linksScope,
        showProgressLine: this.showProgressLine,
        labelColWidth: this.labelColWidth,
        dayWidthOverride: this.dayWidthOverride,
        printPaperSize: this.printPaperSize,
      })
    },
    zoomLabel(z: string): string {
      return z.charAt(0).toUpperCase() + z.slice(1)
    },
    barTitle(a: Activity): string {
      return `${a.task_code} — ${a.task_name}\n${formatDate(displayStart(a))} → ${formatDate(displayEnd(a))}\n` +
        `Duration: ${formatHours(a.duration_hrs, a.calendar_hrs_per_day)} · Float: ${formatFloat(a.total_float_hrs, a.calendar_hrs_per_day)} · ${a.pct_complete}% complete`
    },
    milestoneTitle(a: Activity): string {
      return `${a.task_code} — ${a.task_name}\n${formatDate(displayStart(a))}\nFloat: ${formatFloat(a.total_float_hrs, a.calendar_hrs_per_day)}`
    },
    // Same 0h / negative / ≤80h(10d) severity bands used everywhere else in the app,
    // applied to the whole stat tile so float is legible without reading the number.
    formatDate,
    formatDateShort,
    formatLag,
    formatHours,
    formatFloat,
    statusLabel,
    relTypeLabel,
    cstrLabel,
    displayStart,
    displayEnd,
    severityLabel(s: Severity): string { return SEVERITY_LABELS[s] },
    // Selects a predecessor/successor from the detail panel: expands every WBS
    // ancestor so the row actually renders (it may be tucked under a collapsed
    // branch, or hidden by an active filter), then scrolls to it.
    revealAndSelect(taskId: number) {
      const a = this.actLookup.get(taskId)
      if (!a) return
      if (this.isolationActive) {
        // Chain tracing: clicking a predecessor/successor ADDS it to the traced set and
        // walks the selection onto it, growing the chain one link at a time.
        const next = new Set(this.isolatedIds)
        next.add(taskId)
        this.isolatedIds = next
        this.selectedTaskId = taskId
        this.$nextTick(() => this.scrollToActivity(taskId))
        return
      }
      if (this.isFilterActive) this.clearFilters()
      const toExpand = new Set(this.expandedWbs)
      let cur: number | null = a.wbs_id
      while (cur != null) {
        toExpand.add(cur)
        cur = this.wbsParentOf.get(cur) ?? null
      }
      this.expandedWbs = toExpand
      this.selectedTaskId = taskId
      this.$nextTick(() => this.scrollToActivity(taskId))
    },

    // ── Zoom (presets + continuous) ──────────────────────────────────────
    selectZoomPreset(z: Zoom) {
      this.zoom = z
      this.dayWidthOverride = null
    },
    setDayWidth(v: number) {
      this.dayWidthOverride = clampDayWidth(v)
    },
    zoomIn() {
      this.setDayWidth(this.dayWidth * 1.3)
    },
    zoomOut() {
      this.setDayWidth(this.dayWidth / 1.3)
    },
    fitToWidth() {
      const el = this.$refs.scrollEl as HTMLElement | undefined
      if (!el) return
      const availableWidth = Math.max(100, el.clientWidth - this.labelColWidth)
      const totalDays = Math.max(1, (this.rangeEnd.getTime() - this.rangeStart.getTime()) / 86400000)
      this.setDayWidth(availableWidth / totalDays)
    },
    onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const el = this.$refs.scrollEl as HTMLElement | undefined
      if (!el) return
      const rect = el.getBoundingClientRect()
      const viewportX = e.clientX - rect.left
      const contentXOld = el.scrollLeft + viewportX - this.labelColWidth
      const dateDays = contentXOld / this.dayWidth
      const factor = Math.exp(-e.deltaY * 0.0015)
      this.setDayWidth(this.dayWidth * factor)
      // Chromium can leave position:sticky elements mis-computed if scrollLeft is
      // reassigned in the same tick as the content-width change that just happened
      // (grid-template-columns resize from the new dayWidth). Deferring past two
      // animation frames guarantees a real layout+paint has settled first.
      this.$nextTick(() => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            const contentXNew = dateDays * this.dayWidth
            el.scrollLeft = Math.max(0, contentXNew - viewportX + this.labelColWidth)
          })
        })
      })
    },

    // ── Pan (drag on the timeline; native scrollbars still work too) ────
    onScroll(e: Event) {
      const target = e.target as HTMLElement
      this.scrollLeftPx = target.scrollLeft
      this.scrollTopPx = target.scrollTop
    },
    // ── Note callouts ────────────────────────────────────────────────────
    calloutAnchorX(row: ActivityRow): number {
      return row.milestone ? row.x + 7 : row.x + row.w
    },
    calloutsOf(pg: GridPage): Callout[] {
      const out: Callout[] = []
      for (const row of pg.rows) {
        if (row.type !== 'activity') continue
        const a = this.annotations[row.activity.task_id]
        if (!a?.callout) continue
        const live = this.calloutDrag?.id === row.activity.task_id ? this.calloutDrag : a.callout
        out.push({
          id: row.activity.task_id, code: row.activity.task_code, note: a.note, severity: a.severity,
          ax: this.calloutAnchorX(row) + 7, ay: row.index * ROW_HEIGHT + ROW_HEIGHT / 2,
          dx: live.dx, dy: live.dy,
        })
      }
      return out
    },
    toggleCallout(taskId: number) {
      const open = !!this.annotations[taskId]?.callout
      this.$emit('callout', taskId, open ? null : { ...DEFAULT_CALLOUT })
    },
    onCalloutDragStart(e: MouseEvent, c: Callout) {
      if (e.button !== 0) return
      e.preventDefault()
      this.calloutDrag = { id: c.id, startX: e.clientX, startY: e.clientY, dx0: c.dx, dy0: c.dy, dx: c.dx, dy: c.dy }
      window.addEventListener('mousemove', this.onCalloutDragMove)
      window.addEventListener('mouseup', this.onCalloutDragEnd)
    },
    onCalloutDragMove(e: MouseEvent) {
      const d = this.calloutDrag
      if (!d) return
      d.dx = d.dx0 + e.clientX - d.startX
      d.dy = d.dy0 + e.clientY - d.startY
    },
    onCalloutDragEnd() {
      const d = this.calloutDrag
      window.removeEventListener('mousemove', this.onCalloutDragMove)
      window.removeEventListener('mouseup', this.onCalloutDragEnd)
      if (d && (d.dx !== d.dx0 || d.dy !== d.dy0)) {
        const moved: CalloutOffset = { dx: d.dx, dy: d.dy }
        this.$emit('callout', d.id, moved)
      }
      this.calloutDrag = null
    },

    onPanStart(e: MouseEvent) {
      if (e.button !== 0) return
      const target = e.target as Element
      if (target.closest('.g-label') || target.closest('.g-resize-handle')) return
      this.panning = true
      const st = drag(this)
      // The handler is bound on the scroll element itself, so the ref is mounted.
      const scrollEl = this.$refs.scrollEl as HTMLElement
      st._panStartX = e.clientX
      st._panStartY = e.clientY
      st._panScrollLeft = scrollEl.scrollLeft
      st._panScrollTop = scrollEl.scrollTop
      window.addEventListener('mousemove', this.onPanMove)
      window.addEventListener('mouseup', this.onPanEnd)
    },
    onPanMove(e: MouseEvent) {
      const el = this.$refs.scrollEl as HTMLElement | undefined
      if (!this.panning || !el) return
      const st = drag(this)
      el.scrollLeft = st._panScrollLeft - (e.clientX - st._panStartX)
      el.scrollTop = st._panScrollTop - (e.clientY - st._panStartY)
    },
    onPanEnd() {
      this.panning = false
      window.removeEventListener('mousemove', this.onPanMove)
      window.removeEventListener('mouseup', this.onPanEnd)
    },

    // ── Resizable label column ───────────────────────────────────────────
    onResizeStart(e: MouseEvent) {
      e.preventDefault()
      this.resizing = true
      drag(this)._resizeStartX = e.clientX
      drag(this)._resizeStartWidth = this.labelColWidth
      window.addEventListener('mousemove', this.onResizeMove)
      window.addEventListener('mouseup', this.onResizeEnd)
    },
    onResizeMove(e: MouseEvent) {
      if (!this.resizing) return
      const st = drag(this)
      const dx = e.clientX - st._resizeStartX
      this.labelColWidth = Math.min(labelColMax(), Math.max(LABEL_COL_MIN, st._resizeStartWidth + dx))
    },
    // Double-click on the column edge: widen (or narrow) it to the longest name on screen.
    fitLabelColumn() {
      const names = (this.$el as HTMLElement).querySelectorAll<HTMLElement>('.g-label .g-act-name, .g-label .g-wbs-name')
      if (!names.length) return
      // Measure the text itself: an element that already fits reports no overflow, and the
      // fit must be able to narrow the column as well as widen it.
      const ctx = document.createElement('canvas').getContext('2d')
      if (!ctx) return
      let slack = -Infinity
      for (const n of names) {
        ctx.font = getComputedStyle(n).font
        slack = Math.max(slack, Math.ceil(ctx.measureText(n.textContent || '').width) - n.clientWidth)
      }
      this.labelColWidth = Math.min(labelColMax(), Math.max(LABEL_COL_MIN, this.labelColWidth + slack + 2))
      this.persistView()
    },
    onResizeEnd() {
      if (!this.resizing) return
      this.resizing = false
      window.removeEventListener('mousemove', this.onResizeMove)
      window.removeEventListener('mouseup', this.onResizeEnd)
      this.persistView()
    },
  },
})
</script>

<style scoped>
.gantt-wrap { border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; background: var(--white); margin-bottom: var(--space-6); box-shadow: 0 1px 3px rgba(28,25,23,0.06); font-family: var(--font-ui); }
.gantt-wrap.is-fullscreen { border-radius: 0; display: flex; flex-direction: column; height: 100vh; }
.gantt-wrap.is-fullscreen .gantt-body { flex: 1; min-height: 0; display: flex; }
/* ── Toolbar: one row ─────────────────────────────────────────────────────── */
.gantt-toolbar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 7px var(--space-4); background: var(--panel); border-bottom: 1px solid var(--line); }
.tb-div { width: 1px; align-self: stretch; background: var(--line); margin: 0 2px; }
.tb-group { display: flex; align-items: center; gap: 4px; }
.tb-group-label { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin-right: 2px; }
.tb-right { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.tb-right .filter-input { width: 172px; }
.tb-more { font-size: 15px; line-height: 1; padding: 4px 9px; }

/* Popovers: filters and overflow */
.tb-pop { position: relative; }
.tb-panel { position: absolute; right: 0; top: calc(100% + 5px); min-width: 250px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-md); box-shadow: 0 10px 30px -12px rgba(0,0,0,0.35); padding: var(--space-3); z-index: 12; display: flex; flex-direction: column; gap: 7px; }
.fp-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); font: var(--text-small); color: var(--ink-2); }
.fp-row > span { white-space: nowrap; }
.fp-row .filter-select { min-width: 132px; }
.fp-sep { height: 1px; background: var(--line); margin: 2px 0; }
.tb-panel-menu button { text-align: left; background: none; border: none; border-radius: var(--radius-sm); padding: 6px 8px; cursor: pointer; font: var(--text-small); color: var(--ink-2); }
.tb-panel-menu button:hover:not(:disabled) { background: var(--chip); color: var(--ink); }
.tb-panel-menu button:disabled { opacity: 0.45; cursor: default; }

/* ── Active-filter strip ──────────────────────────────────────────────────── */
.filter-strip { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 34px; padding: 5px var(--space-4); background: var(--panel-2); border-bottom: 1px solid var(--line); }
.fs-label { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; color: var(--ink-3); }
.fs-chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--accent); background: var(--accent-soft); color: var(--accent); border-radius: 14px; padding: 2px 5px 2px 10px; cursor: pointer; font: var(--text-small); font-weight: 600; }
.fs-chip:hover { background: var(--panel); }
.fs-x { font-size: 14px; line-height: 1; opacity: 0.75; }
.filter-strip .fb-search { width: 140px; padding: 3px 8px; }
.filter-strip .fb-select { height: 26px; padding: 0 4px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink-2); max-width: 128px; }
.filter-strip .fb-select.set { max-width: 180px; }
.filter-strip .tb-chip { padding: 3px 9px; }
.fb-dates { display: inline-flex; align-items: center; gap: 2px; }
.filter-strip .fb-dates .filter-date { height: 26px; box-sizing: border-box; padding: 0 3px; width: 122px; }
.fb-dash { color: var(--ink-3); }
.filter-strip .set, .fb-dates.set .filter-date { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.filter-strip .filter-count { margin-left: auto; white-space: nowrap; font: var(--text-small); color: var(--ink-3); font-family: var(--font-mono); }


.gantt-wrap.is-fullscreen .gantt-scroll { flex: 1; height: auto; max-height: none; }

/* Wraps just the scroll viewport so the detail drawer can anchor to its exact bounds
   (top/bottom) regardless of how tall the strip/controls/filter-bar above it are. */
.gantt-body { position: relative; display: flex; align-items: stretch; }

/* Thin ink strip: title + the one highest-value toggle. Everything else lives in the
   light control row below, so there's no large dark panel to justify visually. */

.basis-group { display: flex; align-items: center; gap: 6px; border: 1px solid var(--ink-soft); border-radius: var(--radius-sm); padding: 2px; flex-shrink: 0; }
.basis-group button { padding: 4px 10px; border: none; border-radius: 3px; background: none; cursor: pointer; font: var(--text-small); color: var(--ink-2); }
.basis-group button.active { background: var(--crit); color: var(--on-solid); font-weight: 700; }
.basis-group button:hover:not(.active) { background: var(--ink-soft); }

/* Light control row: legend + every interactive control, directly adjoining the light
   timeline header below — no light/dark/light seam. */
.legend { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 5px; font: var(--text-small); color: var(--gray-700); }
/* Legend swatches ARE miniature bars — same fills and borders as the chart itself, so
   the legend teaches the encoding instead of adding a second one to decode. */
.lg-bar { width: 20px; height: 10px; border-radius: 3px; display: inline-block; box-sizing: border-box; border: 1.5px solid; }
.lg-critical { background: var(--crit-tint); border-color: var(--crit); }
.lg-near { background: var(--near-tint); border-color: var(--near); }
.lg-normal { background: var(--accent-soft); border-color: var(--accent); }
.lg-negative { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.45) 0 2px, transparent 2px 5px), var(--crit); border-color: var(--crit-deep); }
.diamond { width: 8px; height: 8px; background: var(--milestone); display: inline-block; transform: rotate(45deg); }
.bar-wbs { width: 16px; height: 7px; border-radius: 3px; background: var(--gray-700); display: inline-block; }
.progress-swatch { width: 14px; height: 2px; background: var(--milestone); display: inline-block; }

.zoom-group { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; }
.zoom-group button { padding: 4px 10px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); }
.zoom-group button:last-child { border-right: none; }
.zoom-group button.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.zoom-group button:hover:not(.active) { background: var(--gray-150); }
.zoom-adjust { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; }
.zbtn { padding: 4px 10px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); font-weight: 700; }
.zbtn:last-child { border-right: none; }
.zbtn:hover { background: var(--gray-150); }

.filter-input { padding: 6px 12px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); width: 240px; }
.filter-date { border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 4px 6px; background: var(--white); font-family: var(--font-mono); font-size: 12px; color: var(--ink); }
.la-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 700; }
.filter-select { padding: 6px 8px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); }
.filter-check { font: var(--text-small); color: var(--gray-700); display: flex; align-items: center; gap: 4px; cursor: pointer; }
.filter-count { font: var(--text-small); color: var(--gray-500); margin-left: auto; }
.return-chip { display: inline-flex; align-items: center; background: var(--nav); color: var(--nav-ink); border: none; border-radius: 12px; padding: 3px 12px; font: var(--text-small); font-weight: 600; cursor: pointer; }
.return-chip:hover { opacity: 0.9; }
.isolation-chip { display: inline-flex; align-items: center; gap: 8px; background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); border-radius: 12px; padding: 2px 4px 2px 10px; font: var(--text-small); font-weight: 600; }
.isolation-exit { border: none; background: var(--accent); color: var(--on-solid); border-radius: 9px; padding: 2px 9px; font: var(--text-small); font-weight: 600; cursor: pointer; }
.isolation-exit:hover { opacity: 0.9; }

/* Fixed height, not max-height: with a collapsed WBS the viewport used to shrink to
   the handful of visible rows, leaving a cramped partial canvas. A constant-height
   viewport keeps the full working area available no matter how much is expanded. */
.gantt-scroll { flex: 1; min-width: 0; overflow: auto; scrollbar-width: thin; scrollbar-color: var(--line) transparent; height: calc(100dvh - 288px); min-height: 320px; position: relative; cursor: grab; }
.gantt-scroll.panning { cursor: grabbing; }
/* Controls + filter bar wrap taller on narrow screens — leave more room above the grid */
@media (max-width: 900px) {
  .gantt-scroll { height: calc(100dvh - 400px); min-height: 320px; }
}
.gantt-grid { display: grid; grid-template-rows: 56px; grid-auto-rows: 26px; position: relative; }

.g-cell { min-width: 0; }
.g-corner { position: absolute; z-index: 7; background: var(--panel-2); border-bottom: 1px solid var(--line); border-right: 2px solid var(--line); height: 56px; display: flex; align-items: flex-end; gap: 6px; padding: 0 8px 8px 8px; box-sizing: border-box; overflow: hidden; box-shadow: 2px 0 5px -3px rgba(28,25,23,0.18); }
.g-corner-name { flex: 1; min-width: 0; font: var(--text-micro); font-weight: 700; color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.g-corner-col { font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; color: var(--gray-700) !important; }
.g-timeline-header { position: absolute; z-index: 6; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); height: 52px; }
.g-header-band-row { position: relative; height: 26px; border-bottom: 1px solid var(--line-soft); }
.g-header-detail-row { position: relative; height: 30px; }
.g-band-tick { position: absolute; top: 0; height: 100%; padding-left: 6px; padding-top: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2); border-left: 1px solid var(--line); white-space: nowrap; }
.g-dd-chip { position: absolute; top: 4px; transform: translateX(1px); background: var(--ms); color: var(--on-solid); font-family: var(--font-mono); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px; white-space: nowrap; z-index: 2; }
.g-detail-tick { position: absolute; top: 0; padding-top: 8px; padding-left: 4px; font: var(--text-micro); color: var(--gray-700); white-space: nowrap; border-left: 1px solid var(--gray-150); height: 100%; box-sizing: border-box; }
.g-detail-tick.weekend { color: var(--crit); font-weight: 700; }

.g-overlay { position: absolute; pointer-events: none; }
.g-overlay-bg { z-index: 1; }
.g-overlay-fg { z-index: 3; }
.g-weekend { fill: var(--gray-150); }
.g-gridline { stroke: var(--gray-150); stroke-width: 1; }
.g-gridline-month { stroke: var(--gray-300); stroke-width: 1; }
.g-link { fill: none; stroke: var(--crit); stroke-width: 1.5; opacity: 0.75; }
.g-link-arrow { fill: var(--crit); }
.g-link.g-link-chain { stroke: var(--accent); stroke-width: 1.5; opacity: 0.85; }
.g-link-arrow-chain { fill: var(--accent); }
.g-progress-line { fill: none; stroke: var(--milestone); stroke-width: 2; stroke-dasharray: 4 3; opacity: 0.9; }
.g-progress-dot { fill: var(--milestone); }

.g-today-line { position: absolute; width: 2px; background: var(--accent); z-index: 4; pointer-events: none; }
.g-dd-line { position: absolute; width: 0; border-left: 2px dashed var(--milestone); z-index: 4; pointer-events: none; }
.g-dd-flag { position: absolute; top: 2px; left: 3px; font: var(--text-micro); font-weight: 700; color: var(--on-solid); background: var(--milestone); padding: 0 5px; border-radius: var(--radius-sm); white-space: nowrap; }
.g-today-flag { position: absolute; top: -18px; left: 2px; font: var(--text-micro); font-weight: 700; color: var(--accent); white-space: nowrap; }

.g-resize-handle { position: absolute; top: 0; width: 7px; margin-left: -3px; cursor: col-resize; z-index: 8; background: transparent; }
.g-resize-handle:hover, .g-resize-handle.resizing { background: var(--accent-soft); }

.g-label { position: absolute; z-index: 5; background: var(--panel); display: flex; align-items: center; gap: 6px; height: 26px; border-bottom: 1px solid var(--gray-150); border-right: 2px solid var(--gray-300); font: var(--text-small); white-space: nowrap; overflow: hidden; cursor: pointer; box-sizing: border-box; box-shadow: 2px 0 5px -3px rgba(28,25,23,0.1); }
.g-label:hover { background: var(--accent-soft); }
.g-label.selected { background: var(--accent-soft); }
.g-label-wbs { font-weight: 600; background: var(--panel-2); border-bottom: 1px solid var(--line); }

.g-label-wbs:hover { background: var(--accent-soft); }
.g-toggle { color: var(--gray-500); flex-shrink: 0; }
.g-wbs-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--ink); }
.g-wbs-count { padding-right: 4px; font: var(--text-micro); color: var(--gray-500); flex-shrink: 0; }
.g-act-code { font-family: var(--font-mono); font-size: 12px; color: var(--gray-500); flex-shrink: 0; }
.annotation-hit { border: none; background: none; padding: 4px; margin: -4px; cursor: pointer; display: inline-flex; flex-shrink: 0; }
.annotation-hit:hover .annotation-flag { transform: scale(1.5); }
.g-note-dot { position: absolute; top: 50%; margin: 0; transform: translateY(-50%); z-index: 1; }
.g-note-dot .annotation-flag { width: 7px; height: 7px; box-shadow: 0 0 0 1.5px var(--panel); }
.g-callout { position: absolute; z-index: 4; max-width: 230px; min-width: 120px; background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--gray-500); border-radius: var(--radius-sm); box-shadow: 0 6px 18px -8px rgba(0,0,0,0.35); padding: 4px 6px 5px 7px; cursor: move; user-select: none; font: var(--text-small); color: var(--ink); }
.g-callout.sev-query { border-left-color: var(--active); }
.g-callout.sev-risk { border-left-color: var(--near); }
.g-callout.sev-logic { border-left-color: var(--crit); }
.g-callout.sev-resolved { border-left-color: var(--ok); }
.g-callout-head { display: flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); }
.g-callout-sev { font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.g-callout-x { margin-left: auto; border: none; background: none; cursor: pointer; color: var(--ink-3); font-size: 14px; line-height: 1; padding: 0 2px; }
.g-callout-x:hover { color: var(--ink); }
.g-callout-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.35; margin-top: 1px; }
.g-callout-leader { stroke: var(--ink-3); stroke-width: 1; stroke-dasharray: 3 2; }
.annotation-flag { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--gray-500); }
.annotation-flag.sev-query { background: var(--active); }
.annotation-flag.sev-risk { background: var(--near); }
.annotation-flag.sev-logic { background: var(--crit); }
.annotation-flag.sev-resolved { background: var(--ok); }
.g-act-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--ink-soft); }
.g-col-dur, .g-col-date, .g-col-float { flex-shrink: 0; text-align: right; font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); }
.g-col-float { width: 44px; margin-right: 8px; }
.g-col-float.fl-crit { color: var(--crit); font-weight: 700; }
.g-col-float.fl-neg { color: var(--crit); font-weight: 700; }
.g-col-float.fl-near { color: var(--near); font-weight: 600; }
.g-col-dur { width: 34px; }
.g-col-slip { flex-shrink: 0; width: 40px; margin-right: 8px; text-align: right; font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); }
.g-col-slip.slip-late { color: var(--crit); font-weight: 700; }
.g-col-slip.slip-early { color: var(--ok); font-weight: 600; }
.g-col-slip.slip-new { color: var(--gray-500); font-style: italic; }
.g-col-date { width: 48px; }


.g-timeline-row { position: relative; height: 26px; border-bottom: 1px solid var(--gray-150); z-index: 2; }

.g-empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-2); z-index: 6; background: var(--white); }
.g-empty-title { font: var(--text-h3); color: var(--ink); margin: 0; }
.g-empty-sub { font: var(--text-small); color: var(--gray-700); margin: 0; }
.g-float-tail { position: absolute; top: 13px; height: 0; border-top: 1px dashed var(--float-tail); pointer-events: auto; }
.g-bar-ghost { position: absolute; top: 20px; height: 4px; border-radius: 2px; background: transparent; border: 1.5px solid var(--gray-500); box-sizing: border-box; pointer-events: auto; }
.g-milestone-ghost { position: absolute; top: 16px; width: 7px; height: 7px; transform: translateX(-4px) rotate(45deg); border: 1.5px solid var(--gray-500); background: transparent; box-sizing: border-box; }
.lg-ghost { background: transparent !important; border-color: var(--gray-500) !important; height: 5px !important; }
.g-bar { position: absolute; top: 7px; height: 12px; border-radius: var(--radius-sm); overflow: hidden; background: var(--accent-soft); border: 1.5px solid var(--accent); box-sizing: border-box; box-shadow: 0 1px 2px rgba(28,25,23,0.15); }
.g-bar.critical { background: var(--crit-tint); border-color: var(--crit); }
.g-bar.near { background: var(--near-tint); border-color: var(--near); }
.g-bar.other { background: var(--accent-soft); border-color: var(--accent); }
.g-bar.negative { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.45) 0 2px, transparent 2px 5px), var(--crit); border-color: var(--crit-deep); }
.g-bar.negative .g-bar-progress { background: rgba(28,25,23,0.45); }
.g-bar.selected { box-shadow: 0 0 0 2px var(--ink); }
.g-bar-progress { height: 100%; background: rgba(28,25,23,0.28); }

.g-bar-wbs { position: absolute; top: 10px; height: 6px; border-radius: 3px; background: var(--gray-700); }
.g-bar-wbs::before, .g-bar-wbs::after { content: ''; position: absolute; top: 100%; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid var(--gray-700); }
.g-bar-wbs::before { left: -1px; }
.g-bar-wbs::after { right: -1px; }

.g-milestone { position: absolute; top: 8px; width: 11px; height: 11px; margin-left: -5px; background: var(--milestone); transform: rotate(45deg); border-radius: 2px; box-shadow: 0 1px 2px rgba(28,25,23,0.2); }
.g-milestone.critical { background: var(--crit); }
.g-milestone.near { background: var(--near); }
.g-milestone.negative { background: var(--crit); box-shadow: 0 0 0 2px var(--white), 0 0 0 3.5px var(--crit); }


.detail-actions { margin-top: 10px; }
.btn-isolate { color: var(--accent); border-color: var(--accent); font-weight: 600; }
.btn-isolate:hover { background: var(--accent-soft); }
.trace-hint { display: block; font-size: 13px; color: var(--accent); font-weight: 600; background: var(--accent-soft); border-radius: var(--radius-sm); padding: 6px 9px; }

/* Duration/float lead the grid — the two numbers a reviewer needs first, sized to read
   at a glance instead of buried in an inline sentence. */


.print-title { display: none; }

@media print {
  @page { size: landscape; margin: 10mm; }
  .view-bar, .gantt-toolbar, .filter-strip, .g-empty, .g-resize-handle, .g-callout-x { display: none !important; }
  .gantt-wrap, .gantt-wrap.is-fullscreen { border: none; box-shadow: none; height: auto; overflow: visible; display: block; }
  .gantt-body { display: block !important; }
  /* The printout is the screen's grid, drawn once per sheet (gridPages): each sheet is a
     self-contained block of fixed height with its own header and its own links overlay,
     clipped to its rows. Never one grid paginated by the browser: a single canvas whose
     absolutely placed rows and overlay span several sheets is what Chromium printed
     wrongly (a repeated fixed header hid rows; a scale-to-fit transform corrupted the
     links). */
  .gantt-scroll { height: auto !important; min-height: 0 !important; overflow: visible !important; }
  .gantt-print-page { break-after: page; break-inside: avoid; }
  .gantt-print-page.gantt-print-last { break-after: auto; }
  .print-title { display: flex; flex-wrap: wrap; gap: 0 16px; align-items: baseline; height: 18px; margin-bottom: 6px; overflow: hidden; white-space: nowrap; font: 11px/18px var(--font-ui); color: var(--ink-soft); }
  .print-title strong { font-size: 13px; color: var(--ink); }
  .print-pageno { margin-left: auto; font-family: var(--font-mono); }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
</style>
