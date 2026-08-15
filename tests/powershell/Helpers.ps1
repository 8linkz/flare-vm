# Test helpers for install.ps1.
#
# install.ps1 executes its main flow on load (param block + installation logic), so it must not be
# dot-sourced directly in tests. Instead we parse the file with the PowerShell AST and pull out the
# source text of individual functions, then evaluate only those in the test scope.

function Get-InstallScriptPath {
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..\install.ps1')).Path
}

function Get-InstallFunctionText {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$InstallPath = (Get-InstallScriptPath)
    )
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($InstallPath, [ref]$tokens, [ref]$errors)
    $fn = $ast.FindAll(
        { param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $Name },
        $true
    ) | Select-Object -First 1
    if (-not $fn) {
        throw "Function '$Name' not found in $InstallPath"
    }
    return $fn.Extent.Text
}

function Import-InstallFunction {
    # Define the named install.ps1 function(s) in the GLOBAL scope so they are visible to Pester It
    # blocks regardless of the scope this helper is called from. Test files should remove them in an
    # AfterAll if isolation across files matters.
    param([Parameter(Mandatory = $true)][string[]]$Name)
    foreach ($n in $Name) {
        $text = Get-InstallFunctionText -Name $n
        # Inject the global: scope modifier into the function definition header.
        $globalText = $text -replace "^\s*function\s+$([regex]::Escape($n))", "function global:$n"
        . ([ScriptBlock]::Create($globalText))
    }
}
