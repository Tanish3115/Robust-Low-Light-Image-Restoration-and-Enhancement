param([string]$InputDocx, [string]$OutputPdf)
$ErrorActionPreference = 'Stop'
$wordReport = $null
$reportDocument = $null
try {
    $wordReport = New-Object -ComObject Word.Application
    $wordReport.Visible = $false
    $wordReport.DisplayAlerts = 0
    $wordReport.AutomationSecurity = 3
    $reportDocument = $wordReport.Documents.Open($InputDocx, $false, $true)
    $reportDocument.ExportAsFixedFormat($OutputPdf, 17)
    Write-Output "Exported report to PDF."
} finally {
    if ($reportDocument) { $reportDocument.Close(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($reportDocument) }
    if ($wordReport) { $wordReport.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordReport) }
}
