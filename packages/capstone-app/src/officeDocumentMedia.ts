export const docxMedia='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
export const openDocumentMedia={
  odt:'application/vnd.oasis.opendocument.text',
  ods:'application/vnd.oasis.opendocument.spreadsheet',
  odp:'application/vnd.oasis.opendocument.presentation',
}
export const officeDocumentMedia=new Set([docxMedia,...Object.values(openDocumentMedia)])
