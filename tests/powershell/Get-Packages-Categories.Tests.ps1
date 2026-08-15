# Tests for Get-Packages-Categories in install.ps1.
# Covers the feed-robustness fixes for issues #709 / #695 / #736 / #697: a failed/empty/malformed
# MyGet package feed must abort with a clear error instead of crashing or silently showing no packages.

BeforeAll {
    . $PSScriptRoot\Helpers.ps1
    Import-InstallFunction -Name 'Save-FileFromUrl', 'Get-Packages-Categories'

    # $excludedCategories is intentionally left undefined: in Get-Packages-Categories the filter
    # ($excludedCategories -notcontains $category) then evaluates against $null, which excludes nothing.
    # Save-FileFromUrl and Get-Content are mocked, so the on-disk feed path is irrelevant.

    $script:validFeed = @'
<?xml version="1.0" encoding="utf-8"?>
<feed xml:base="https://www.myget.org/F/vm-packages/api/v2"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <m:properties>
      <d:Id>testpkg.vm</d:Id>
      <d:Description>A test package</d:Description>
      <d:IsLatestVersion m:type="Edm.Boolean">true</d:IsLatestVersion>
      <d:Tags>Analysis</d:Tags>
      <d:projectUrl>https://example.com/testpkg</d:projectUrl>
    </m:properties>
  </entry>
</feed>
'@

    $script:zeroEntryFeed = '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
}

Describe 'Get-Packages-Categories' {
    It 'parses a valid feed into a category -> packages hashtable' {
        Mock Save-FileFromUrl {}
        Mock Get-Content { $script:validFeed }

        $result = Get-Packages-Categories

        $result['Analysis'][0].PackageName | Should -Be 'testpkg.vm'
    }

    It 'aborts with a clear error when the feed content is empty or malformed' {
        Mock Save-FileFromUrl {}
        Mock Get-Content { '' }

        { Get-Packages-Categories } | Should -Throw -ExpectedMessage '*could not be read*'
    }

    It 'aborts with a clear error when the feed contains no package entries' {
        Mock Save-FileFromUrl {}
        Mock Get-Content { $script:zeroEntryFeed }

        { Get-Packages-Categories } | Should -Throw -ExpectedMessage '*no packages*'
    }
}
