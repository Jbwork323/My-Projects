# Script to retrieve Active Directory users with phone numbers not matching 3039146xxx
# Script only retrieves employees because students don't have phone numbers in AD 
# but will need to be changed if that changes in the future
# Requires Active Directory PowerShell Module

# Import the Active Directory Module
Import-Module ActiveDirectory

# Function to get users with non DID phone numbers
function Get-ADUsersWithNonMatchingPhones {
    param (
        [string]$OrganizationalUnit = "OU=RRC_OU_Users,OU=RRCC,DC=ccc,DC=ccofc,DC=edu", # Specific OU for RRCC
        [string]$ExpectedPattern = "3039146\d{3}", # Regex pattern to match DID phone numbers
        [string]$SpecialCasePattern = "\(303\)914-6\d{3}", # Pattern to include one specific incorrectly formatted number
        [switch]$IncludeDisabled = $false # Dont include disabled user accounts
    )

    # Base filter for users with phone numbers
    $filter = "TelephoneNumber -like '*'"   

    # Add filter for enabled/disabled user accounts if needed
    if (-not $IncludeDisabled) {
        $filter += " -and Enabled -eq 'True'"
    }

    try {
        # Retrieve users where phone number doesn't match pattern 3039146xxx
        $allUsersWithPhones = Get-ADUser -Filter $filter `
            -Properties SamAccountName, 
                        Name, 
                        TelephoneNumber, 
                        Mail, 
                        Department `
            -SearchBase $OrganizationalUnit | 
            Where-Object { 
                $_.TelephoneNumber -notmatch $ExpectedPattern  -and 
                ($_.TelephoneNumber -notmatch $SpecialCasePattern)
            } |
            Select-Object SamAccountName, 
                          Name, 
                          TelephoneNumber, 
                          Mail, 
                          Department
        
        return $allUsersWithPhones
    }
    catch {
        Write-Error "Error retrieving AD users: $_"
        return $null
    }
}

# get list of users with non DID numbers
try {
    # Retrieve users with phone numbers not matching the pattern
    $nonMatchingPhoneUsers = Get-ADUsersWithNonMatchingPhones

    # Display results
    if ($nonMatchingPhoneUsers) {
        Write-Host "Users with Non-DID Phone Numbers:" -ForegroundColor Green
        $nonMatchingPhoneUsers | Format-Table -AutoSize

        # Export to CSV
        $exportPath = "C:\Temp\RRCC_Users_NonDID_Phones_$(Get-Date -Format 'yyyyMMdd').csv"
        $nonMatchingPhoneUsers | Export-Csv -Path $exportPath -NoTypeInformation
        Write-Host "Exported results to $exportPath" -ForegroundColor Cyan

        # Display total count
        Write-Host "Total users with non-DID phone numbers: $($nonMatchingPhoneUsers.Count)" -ForegroundColor Cyan
    }
    else {
        Write-Host "No users found with non-DID phone numbers." -ForegroundColor Yellow
    }
}
catch {
    Write-Error "Script execution failed: $_"
}