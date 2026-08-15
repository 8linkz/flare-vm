# Tests for the package-list helper functions in install.ps1.
# These functions read script-scoped lists ($packagesByCategory, $packagesToInstall, $listedPackages);
# PowerShell dynamic scoping lets the extracted functions read those variables from the calling It scope,
# so no global variables are needed. `choco` is mocked; nothing hits the network or the real feed.

[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '',
    Justification = 'These variables are read by the install.ps1 functions under test via PowerShell dynamic scoping, which the analyzer cannot see.')]
param()

BeforeAll {
    . $PSScriptRoot\Helpers.ps1
    Import-InstallFunction -Name @(
        'Get-AllPackages',
        'Get-AdditionalPackages',
        'Get-PackagesByCategory',
        'Get-VMPackage',
        'Get-ChocoPackage',
        'Get-ConfigFile',
        'Save-FileFromUrl'
    )
}

Describe 'Get-AllPackages' {
    It 'returns every package name across all categories' {
        $packagesByCategory = @{
            'Analysis'  = @([pscustomobject]@{ PackageName = 'a.vm' }, [pscustomobject]@{ PackageName = 'b.vm' })
            'Debuggers' = @([pscustomobject]@{ PackageName = 'c.vm' })
        }
        $result = Get-AllPackages
        $result.Count | Should -Be 3
        $result | Should -Contain 'a.vm'
        $result | Should -Contain 'b.vm'
        $result | Should -Contain 'c.vm'
    }
}

Describe 'Get-AdditionalPackages' {
    It 'returns config packages that are not shown in the category list' {
        $packagesToInstall = @('a.vm', 'b.vm', 'choco-only')
        $listedPackages = @('a.vm', 'b.vm')
        Get-AdditionalPackages | Should -Be @('choco-only')
    }

    It 'returns nothing when every config package is already listed' {
        $packagesToInstall = @('a.vm', 'b.vm')
        $listedPackages = @('a.vm', 'b.vm')
        Get-AdditionalPackages | Should -BeNullOrEmpty
    }
}

Describe 'Get-PackagesByCategory' {
    It 'returns the packages for the given category' {
        $packagesByCategory = @{ 'Analysis' = @('x.vm', 'y.vm') }
        Get-PackagesByCategory -category 'Analysis' | Should -Be @('x.vm', 'y.vm')
    }

    It 'returns nothing for an unknown category' {
        $packagesByCategory = @{ 'Analysis' = @('x.vm') }
        Get-PackagesByCategory -category 'DoesNotExist' | Should -BeNullOrEmpty
    }
}

Describe 'Get-VMPackage' {
    It 'appends .vm to a bare package name before searching' {
        Mock choco { "$($args[1])|1.0" }   # echo the search term as the package name
        (Get-VMPackage -PackageName '7zip').Name | Should -Be '7zip.vm'
    }

    It 'does not double-append .vm when the name already ends in .vm' {
        Mock choco { "$($args[1])|1.0" }
        (Get-VMPackage -PackageName '7zip.vm').Name | Should -Be '7zip.vm'
    }

    It 'parses the version from the choco output' {
        Mock choco { '7zip.vm|19.00' }
        (Get-VMPackage -PackageName '7zip').Version | Should -Be '19.00'
    }
}

Describe 'Get-ChocoPackage' {
    It 'parses each choco search line into a name/version object' {
        Mock choco { '7zip|19.00', 'git|2.44' }
        $result = Get-ChocoPackage -PackageName 'anything'
        ($result | Measure-Object).Count | Should -Be 2
        $result[0].Name | Should -Be '7zip'
        $result[0].Version | Should -Be '19.00'
    }
}

Describe 'Get-ConfigFile' {
    It 'moves the file locally when the source path exists' {
        Mock Write-Host {}
        Mock Test-Path { $true }
        Mock Move-Item {}
        Mock Save-FileFromUrl {}
        Get-ConfigFile -fileDestination 'dest.xml' -fileSource 'C:\local\config.xml'
        Should -Invoke Move-Item -Times 1 -Exactly
        Should -Invoke Save-FileFromUrl -Times 0 -Exactly
    }

    It 'downloads the file when the source is not an existing path' {
        Mock Write-Host {}
        Mock Test-Path { $false }
        Mock Move-Item {}
        Mock Save-FileFromUrl {}
        Get-ConfigFile -fileDestination 'dest.xml' -fileSource 'https://example.com/config.xml'
        Should -Invoke Save-FileFromUrl -Times 1 -Exactly
        Should -Invoke Move-Item -Times 0 -Exactly
    }
}
