# Tests for the pre-install check functions in install.ps1.
# Each Test-* function returns $null when the check passes, or an error string when it fails.
# All external calls (CIM, services, registry, network, drives) are mocked; nothing touches the real system.

BeforeAll {
    . $PSScriptRoot\Helpers.ps1
    Import-InstallFunction -Name @(
        'Test-PSVersion',
        'Test-ExecutionPolicy',
        'Test-DefenderAndTamperProtection',
        'Test-WindowsVersion',
        'Test-TestedOS',
        'Test-SpaceUserName',
        'Test-Storage',
        'Test-WebConnection'
    )
}

Describe 'Test-PSVersion' {
    It 'returns null on a supported PowerShell version (>= 5)' {
        # The test host runs PowerShell 5.1, so no override is needed for the happy path.
        Test-PSVersion | Should -Be $null
    }

    # The "PowerShell < 5" branch is not unit-tested: the function reads the automatic, read-only
    # $PSVersionTable, which cannot be overridden in the session to simulate an old version without a
    # parameter/injection point in the function. Covering it would require changing production code.
}

Describe 'Test-ExecutionPolicy' {
    It 'returns null when the execution policy is Unrestricted' {
        Mock Get-ExecutionPolicy { 'Unrestricted' }
        Test-ExecutionPolicy | Should -Be $null
    }

    It 'reports an error when the execution policy is not Unrestricted' {
        Mock Get-ExecutionPolicy { 'Restricted' }
        Test-ExecutionPolicy | Should -Match 'enable script execution'
    }
}

Describe 'Test-DefenderAndTamperProtection' {
    It 'reports an error when Windows Defender is running' {
        Mock Get-Service { [pscustomobject]@{ Status = 'Running' } }
        Test-DefenderAndTamperProtection | Should -Match 'Disable Windows Defender'
    }

    It 'reports an error when Tamper Protection is enabled (value 5)' {
        Mock Get-Service { [pscustomobject]@{ Status = 'Stopped' } }
        Mock Get-ItemProperty { [pscustomobject]@{ TamperProtection = 5 } }
        Test-DefenderAndTamperProtection | Should -Match 'Disable Tamper Protection'
    }

    It 'returns null when Defender is stopped and Tamper Protection is off' {
        Mock Get-Service { [pscustomobject]@{ Status = 'Stopped' } }
        Mock Get-ItemProperty { [pscustomobject]@{ TamperProtection = 0 } }
        Test-DefenderAndTamperProtection | Should -Be $null
    }

    It 'reports an error when the Tamper Protection state cannot be read' {
        Mock Get-Service { [pscustomobject]@{ Status = 'Stopped' } }
        Mock Get-ItemProperty { throw 'registry error' }
        Test-DefenderAndTamperProtection | Should -Match 'Unable to determine'
    }
}

Describe 'Test-WindowsVersion' {
    It 'returns null on Windows 10' {
        Mock Get-CimInstance { [pscustomobject]@{ Version = '10.0.19045' } }
        Test-WindowsVersion | Should -Be $null
    }

    It 'reports an error on Windows older than 10' {
        Mock Get-CimInstance { [pscustomobject]@{ Version = '6.1.7601' } }
        Test-WindowsVersion | Should -Match 'Only Windows >= 10 is supported'
    }

    It 'reports an error when the Windows version cannot be determined' {
        Mock Get-CimInstance { throw 'cim error' }
        Test-WindowsVersion | Should -Match 'Unable to determine Windows Version'
    }
}

Describe 'Test-TestedOS' {
    It 'returns null for a tested build number' {
        Mock Get-CimInstance { [pscustomobject]@{ BuildNumber = '19045' } }
        Test-TestedOS | Should -Be $null
    }

    It 'reports an error for an untested build number' {
        Mock Get-CimInstance { [pscustomobject]@{ BuildNumber = '12345' } }
        Test-TestedOS | Should -Match 'has not been tested'
    }

    It 'reports an error when the build number cannot be determined' {
        Mock Get-CimInstance { throw 'cim error' }
        Test-TestedOS | Should -Match 'may not have been tested'
    }
}

Describe 'Test-SpaceUserName' {
    It 'returns null when the username has no space' {
        $original = $env:UserName
        try {
            $env:UserName = 'flare'
            Test-SpaceUserName | Should -Be $null
        } finally {
            $env:UserName = $original
        }
    }

    It 'reports an error when the username contains a space' {
        $original = $env:UserName
        try {
            $env:UserName = 'fl are'
            Test-SpaceUserName | Should -Match 'contains a space'
        } finally {
            $env:UserName = $original
        }
    }
}

Describe 'Test-Storage' {
    It 'returns null when the drive has at least ~60 GB' {
        Mock Start-Sleep {}
        Mock Get-Location { [pscustomobject]@{ Drive = [pscustomobject]@{ Name = 'C' } } }
        Mock Get-PSDrive { [pscustomobject]@{ used = 30GB; free = 40GB } }
        Test-Storage | Should -Be $null
    }

    It 'reports an error when the drive is smaller than ~60 GB' {
        Mock Start-Sleep {}
        Mock Get-Location { [pscustomobject]@{ Drive = [pscustomobject]@{ Name = 'C' } } }
        Mock Get-PSDrive { [pscustomobject]@{ used = 10GB; free = 10GB } }
        Test-Storage | Should -Match 'minimum of 60 GB'
    }

    It 'reports an error when the drive space cannot be determined' {
        Mock Start-Sleep {}
        Mock Get-Location { [pscustomobject]@{ Drive = [pscustomobject]@{ Name = 'C' } } }
        Mock Get-PSDrive { throw 'no such drive' }
        Test-Storage | Should -Match 'Unable to determine hard drive space'
    }
}

Describe 'Test-WebConnection' {
    It 'returns null when the host is reachable and returns HTTP 200' {
        Mock Write-Host {}
        Mock Test-Connection { $true }
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 200 } }
        Test-WebConnection 'github.com' | Should -Be $null
    }

    It 'reports an error when the host cannot be pinged' {
        Mock Write-Host {}
        Mock Test-Connection { $false }
        Test-WebConnection 'github.com' | Should -Match 'cannot ping'
    }

    It 'reports an error when the web request throws' {
        Mock Write-Host {}
        Mock Test-Connection { $true }
        Mock Invoke-WebRequest { throw 'connection reset' }
        Test-WebConnection 'github.com' | Should -Match 'Error accessing'
    }

    It 'reports an error on a non-200 status code' {
        Mock Write-Host {}
        Mock Test-Connection { $true }
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 404 } }
        Test-WebConnection 'github.com' | Should -Match 'Status code: 404'
    }
}
