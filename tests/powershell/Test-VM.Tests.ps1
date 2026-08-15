# Tests for the Test-VM pre-install check in install.ps1 (issue #751: detect QEMU VMs).

BeforeAll {
    . $PSScriptRoot\Helpers.ps1
    Import-InstallFunction -Name 'Test-VM'
}

Describe 'Test-VM' {
    It 'detects a QEMU VM via the manufacturer when the model is not a known virtual model' {
        Mock Get-CimInstance { [pscustomobject]@{ model = 'Standard PC (Q35 + ICH9, 2009)'; manufacturer = 'QEMU' } }
        Test-VM | Should -Be $null
    }

    It 'still detects a VirtualBox VM by model' {
        Mock Get-CimInstance { [pscustomobject]@{ model = 'VirtualBox'; manufacturer = 'innotek GmbH' } }
        Test-VM | Should -Be $null
    }

    It 'reports an error on bare metal (non-virtual model and non-QEMU manufacturer)' {
        Mock Get-CimInstance { [pscustomobject]@{ model = 'Precision 5560'; manufacturer = 'Dell Inc.' } }
        Test-VM | Should -Match 'not on a VM'
    }

    It 'detects a VMware VM by model' {
        Mock Get-CimInstance { [pscustomobject]@{ model = 'VMware Virtual Platform'; manufacturer = 'VMware, Inc.' } }
        Test-VM | Should -Be $null
    }

    It 'detects a Hyper-V VM by the "Virtual Machine" model' {
        Mock Get-CimInstance { [pscustomobject]@{ model = 'Virtual Machine'; manufacturer = 'Microsoft Corporation' } }
        Test-VM | Should -Be $null
    }

    It 'reports an error when the computer system model cannot be read' {
        # A null model makes $computerSystemModel.Contains(...) throw, hitting the catch block.
        Mock Get-CimInstance { [pscustomobject]@{ model = $null; manufacturer = $null } }
        Test-VM | Should -Match 'Unable to determine if you are on a VM'
    }
}
