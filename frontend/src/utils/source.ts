// Which tool wrote the schedule, and the words the UI uses for it. One place, so every
// label that names the tool or the file kind stays honest for P6 and Project files alike.

import type { ProjectSummary, SourceFormat } from '../types/schedule'

type Sourced = Pick<ProjectSummary, 'source_format'>

/** Snapshots saved before 1.2.0 carry no source_format; they are all .xer. */
export function sourceFormat(p: Sourced | null | undefined): SourceFormat {
  const f = p?.source_format
  return f === 'mspdi' || f === 'mpp' || f === 'pmxml' ? f : 'xer'
}

/** A Microsoft Project file (XML or .mpp); P6's .xer and XML are both P6. */
export function isProjectFile(p: Sourced | null | undefined): boolean {
  const f = sourceFormat(p)
  return f === 'mspdi' || f === 'mpp'
}

/** The scheduling tool, for labels such as "P6 scheduling options". */
export function toolName(p: Sourced | null | undefined): string {
  return isProjectFile(p) ? 'Microsoft Project' : 'P6'
}

/** The kind of file, for messages such as "check the file is a P6 .xer export". */
export function fileKind(p: Sourced | null | undefined): string {
  const f = sourceFormat(p)
  return f === 'mpp' ? 'Microsoft Project .mpp file' : f === 'mspdi' ? 'Microsoft Project XML file' : f === 'pmxml' ? 'P6 XML export' : 'P6 .xer export'
}

/** What the file inputs accept; the backend decides by content, the extension only filters the picker. */
export const ACCEPT = '.xer,.xml,.mpp'
export const ACCEPTED_EXTENSIONS = ['.xer', '.xml', '.mpp']
export const DROP_PROMPT = 'Drop a P6 .xer or XML, or a Microsoft Project .mpp or XML file here, or click to browse'

export function hasAcceptedExtension(name: string): boolean {
  const n = name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some(e => n.endsWith(e))
}

/** Why a file can't be opened, from its name; null when it can be tried. Formats people
 *  commonly send instead get a way to export what can be read. */
export function unsupportedFileMessage(name: string): string | null {
  if (hasAcceptedExtension(name)) return null
  const n = name.toLowerCase()
  if (n.endsWith('.pp')) {
    return 'Asta Powerproject (.pp) files can\'t be read. In Powerproject, export the project as Microsoft Project XML and open that file instead.'
  }
  return 'Only .xer, .xml (P6 or Microsoft Project) and .mpp files are accepted'
}
