# Tests for the non-visual logic of GUI helper functions in install.ps1.
# These functions manipulate WinForms controls (a ListBox and checkbox objects) but contain real logic
# (trim + de-duplication, bulk check/uncheck). We drive them with headless WinForms objects / plain
# objects - no window is ever shown.

[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '',
    Justification = 'These variables are read by the install.ps1 functions under test via PowerShell dynamic scoping, which the analyzer cannot see.')]
param()

BeforeAll {
    Add-Type -AssemblyName System.Windows.Forms
    . $PSScriptRoot\Helpers.ps1
    Import-InstallFunction -Name @(
        'Add-NewPackage',
        'Select-AllPackages',
        'Clear-AllPackages',
        'Set-InitialPackages',
        'Set-AdditionalPackages'
    )
}

Describe 'Add-NewPackage' {
    It 'adds a new package and reports success' {
        $additionalPackagesBox = New-Object System.Windows.Forms.ListBox
        Add-NewPackage -packageName 'foo.vm' | Should -BeTrue
        $additionalPackagesBox.Items | Should -Contain 'foo.vm'
    }

    It 'refuses a duplicate package and reports failure' {
        $additionalPackagesBox = New-Object System.Windows.Forms.ListBox
        Add-NewPackage -packageName 'foo.vm' | Out-Null
        Add-NewPackage -packageName 'foo.vm' | Should -BeFalse
        ($additionalPackagesBox.Items | Where-Object { $_ -eq 'foo.vm' }).Count | Should -Be 1
    }

    It 'trims surrounding whitespace before adding' {
        $additionalPackagesBox = New-Object System.Windows.Forms.ListBox
        Add-NewPackage -packageName '  bar.vm  ' | Out-Null
        $additionalPackagesBox.Items | Should -Contain 'bar.vm'
    }
}

Describe 'Select-AllPackages' {
    It 'checks every package checkbox' {
        $checkboxesPackages = @(
            [pscustomobject]@{ Checked = $false },
            [pscustomobject]@{ Checked = $false }
        )
        Select-AllPackages
        $checkboxesPackages[0].Checked | Should -BeTrue
        $checkboxesPackages[1].Checked | Should -BeTrue
    }
}

Describe 'Clear-AllPackages' {
    It 'unchecks every package checkbox and empties the additional-packages list' {
        $checkboxesPackages = @(
            [pscustomobject]@{ Checked = $true },
            [pscustomobject]@{ Checked = $true }
        )
        $additionalPackagesBox = New-Object System.Windows.Forms.ListBox
        $additionalPackagesBox.Items.Add('leftover.vm') | Out-Null

        Clear-AllPackages

        $checkboxesPackages[0].Checked | Should -BeFalse
        $checkboxesPackages[1].Checked | Should -BeFalse
        $additionalPackagesBox.Items.Count | Should -Be 0
    }
}

Describe 'Set-InitialPackages' {
    It 'checks packages that are in the config and unchecks those that are not' {
        $packagesToInstall = @('inconfig.vm')
        $checkboxesPackages = @(
            [pscustomobject]@{ Text = 'inconfig.vm: an installed package'; Checked = $false },
            [pscustomobject]@{ Text = 'notinconfig.vm: a stray selection'; Checked = $true }
        )
        Set-InitialPackages
        $checkboxesPackages[0].Checked | Should -BeTrue   # in config -> checked
        $checkboxesPackages[1].Checked | Should -BeFalse  # not in config -> unchecked
    }

    It 'leaves already-correct checkbox states unchanged' {
        $packagesToInstall = @('inconfig.vm')
        $checkboxesPackages = @(
            [pscustomobject]@{ Text = 'inconfig.vm: desc'; Checked = $true },
            [pscustomobject]@{ Text = 'other.vm: desc'; Checked = $false }
        )
        Set-InitialPackages
        $checkboxesPackages[0].Checked | Should -BeTrue
        $checkboxesPackages[1].Checked | Should -BeFalse
    }
}

Describe 'Set-AdditionalPackages' {
    It 'replaces the list box contents with the additional packages' {
        $additionalPackages = @('a.vm', 'b.vm')
        $additionalPackagesBox = New-Object System.Windows.Forms.ListBox
        $additionalPackagesBox.Items.Add('stale.vm') | Out-Null

        Set-AdditionalPackages

        $additionalPackagesBox.Items.Count | Should -Be 2
        $additionalPackagesBox.Items | Should -Contain 'a.vm'
        $additionalPackagesBox.Items | Should -Contain 'b.vm'
        $additionalPackagesBox.Items | Should -Not -Contain 'stale.vm'
    }
}
