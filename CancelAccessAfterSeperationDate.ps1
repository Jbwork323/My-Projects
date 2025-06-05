# TO USE First set up API key in a powershell window with admin permissions
# using this command [Environment]::SetEnvironmentVariable('JIRA_API_KEY', 'YOUR_API_KEY_HERE', 'Machine')
# then replace the variable $JiraEmail with the email that matches the API key
# Finally, in the Resolve-Ticket section, replace the $comment variable with your own name

# Jira connection parameters
$jiraBaseUrl = "https://jirainstance.atlassian.net"
$JiraEmail = "email@email.com" # set to email that matches API key
#$JiraEmail = "email@email.com"


function Add-SupervisorToJiraTicket {
    param (
        [Parameter(Mandatory = $true)]
        [PSObject]$Ticket,
        
        [Parameter(Mandatory = $true)]
        [string]$SupervisorEmail
    )

    $participantUri = "$jiraBaseUrl/rest/servicedeskapi/request/$($Ticket.Key)/participant"
    $userSearchUri = "$jiraBaseUrl/rest/api/3/user/search?query=$([System.Uri]::EscapeDataString($SupervisorEmail))"

    $headers = @{
        "Authorization" = "Basic $base64AuthInfo"
        "Content-Type" = "application/json"
        "Accept" = "application/json"
    }

    try {
        # Find the user's accountId
        $userResponse = Invoke-RestMethod -Uri $userSearchUri -Method Get -Headers $headers
        if ($userResponse.Count -eq 0) {
            Write-Error "No Jira user found for email $SupervisorEmail"
            return $false
        }
        $accountId = $userResponse[0].accountId

        # Prepare the request body
        $bodyObject = @{
            "accountIds" = @($accountId)
        }
        $bodyJson = $bodyObject | ConvertTo-Json -Depth 10

        # Make the API call
        $response = Invoke-RestMethod -Uri $participantUri -Method Post -Headers $headers -Body $bodyJson
        Write-Host "Successfully added $SupervisorEmail as a request participant to ticket $($Ticket.Key)" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Error "Failed to add supervisor as request participant to ticket $($Ticket.Key). Error: $_"
        Write-Host "StatusCode: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
        return $false
    }
}

# Function to extract employee information from ticket summary/description
function Extract-JiraTicketFields {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [object]$Ticket
    )

    # Initialize result object to match the expected structure in EmployeeTickets function
    $result = [PSCustomObject]@{
        FullName = $null
        PreferredName = $null
        StudentID = $null
        SeparationDate = $null
        SupervisorEmail = $null
        Department = $null
        IsReadyForDeactivation = $false
    }

    try {
        $ticketContent = ""
        
        # Check if the description is in Atlassian Document Format
        if ($Ticket.Description -is [hashtable] -or $Ticket.Description -is [PSCustomObject]) {
            # Convert the ADF to plain text
            $descriptionObj = $Ticket.Description
            
            # Check if it has a 'content' property which is an array
            if ($descriptionObj.content -is [array]) {
                # Recursively extract text from the ADF structure
                function Extract-TextFromADF {
                    param([object]$Node)
                    
                    $extractedText = ""
                    
                    if ($Node.text) {
                        $extractedText += $Node.text
                    }
                    
                    if ($Node.content -and $Node.content -is [array]) {
                        foreach ($child in $Node.content) {
                            $extractedText += Extract-TextFromADF -Node $child
                            
                            # Add newlines for paragraph breaks
                            if ($child.type -eq "paragraph") {
                                $extractedText += "`n"
                            }
                        }
                    }
                    
                    return $extractedText
                }
                
                $ticketContent = Extract-TextFromADF -Node $descriptionObj
            }
            else {
                # If we can't parse it properly, convert the object to a string
                $ticketContent = $Ticket.Description | ConvertTo-Json -Depth 10
            }
        }
        else {
            # If it's already a string, use it directly
            $ticketContent = $Ticket.Description.ToString()
        }
        
        Write-Verbose "Processed ticket content: $ticketContent"

        # Extract Full Name field using regex
        $nameMatch = [regex]::Match($ticketContent, "Name:\s*(.*?)(?:\r?\n|\n)")
        if ($nameMatch.Success) {
            $result.FullName = $nameMatch.Groups[1].Value.Trim()
        }

        # Extract Preferred Name field using regex
        $preferredNameMatch = [regex]::Match($ticketContent, "Preferred Name:\s*(.*?)(?:\r?\n|\n)")
        if ($preferredNameMatch.Success) {
            $result.PreferredName = $preferredNameMatch.Groups[1].Value.Trim()
        }

        # Extract Student ID field using regex
        $studentIDMatch = [regex]::Match($ticketContent, "S#.*?:\s*(.*?)(?:\r?\n|\n)")
        if ($studentIDMatch.Success) {
            $result.StudentID = $studentIDMatch.Groups[1].Value.Trim()
        }

        # Extract Separation Effective Date field using regex
        $dateMatch = [regex]::Match($ticketContent, "Separation Effective Date:\s*(.*?)(?:\r?\n|\n)")
        if ($dateMatch.Success) {
            $dateString = $dateMatch.Groups[1].Value.Trim()
            $result.SeparationDate = $dateString
            
            # Check if the separation date has passed or is today to determine if ready for deactivation
            try {
                $separationDate = [DateTime]::ParseExact(
                    $dateString,
                    "yyyy-M-d", 
                    [System.Globalization.CultureInfo]::InvariantCulture
                )
                
                # Convert to proper DateTime object for the property as well
                $separationDate = $separationDate.Date.AddHours(23).AddMinutes(59)
                $result.SeparationDate = $separationDate
            }
            catch {
                Write-Warning "Could not parse date '$dateString' as DateTime for ticket $($Ticket.Key)"
            }
        }

        # Extract Supervisor Email field using regex
        $supervisorMatch = [regex]::Match($ticketContent, "Supervisor Email:\s*(.*?)(?:\r?\n|\n)")
        if ($supervisorMatch.Success) {
            $result.SupervisorEmail = $supervisorMatch.Groups[1].Value.Trim()
        }

        # Extract Department field using regex
        $departmentMatch = [regex]::Match($ticketContent, "Department:\s*(.*?)(?:\r?\n|\n)")
        if ($departmentMatch.Success) {
            $result.Department = $departmentMatch.Groups[1].Value.Trim()
        }

        return $result
    }
    catch {
        Write-Error "Error processing Jira ticket $($Ticket.Key): $_"
        throw
    }
}

# Function to process tickets and identify accounts for deactivation
function EmployeeTickets {
    param (
        [Parameter(Mandatory=$true)]
        [Array]$Tickets
    )
    
    $ticketsToProcess = @()
    
    foreach ($ticket in $Tickets) {
        Write-Host "`nProcessing ticket: $($ticket.Key)" -ForegroundColor Cyan
        
        $ticketContent = $($ticket.Description)
        Write-Host $ticketContent
        $employeeInfo = Extract-JiraTicketFields -Ticket $ticket
        
        
        # Add ticket info and employee info to the results
        $ticketInfo = [PSCustomObject]@{
            TicketKey = $ticket.Key
            EmployeeInfo = $employeeInfo
        }
        
        # Display extracted information
        Write-Host "  Full Name: $($employeeInfo.FullName)" -ForegroundColor White
        Write-Host "  Preferred Name: $($employeeInfo.PreferredName)" -ForegroundColor White
        Write-Host "  Student ID: $($employeeInfo.StudentID)" -ForegroundColor White
        Write-Host "  Separation Date: $($employeeInfo.SeparationDate)" -ForegroundColor White
        Write-Host "  Supervisor: $($employeeInfo.SupervisorEmail)" -ForegroundColor White
        Write-Host "  Department: $($employeeInfo.Department)" -ForegroundColor White
        
        # add the supervisor to the ticket
        Add-SupervisorToJiraTicket -Ticket $ticket -SupervisorEmail $employeeInfo.SupervisorEmail

        Write-Host "Setting User Expiry Date..." -ForegroundColor Yellow
        Deactivate-User -SNum $employeeInfo.StudentID -SeparationDate $employeeInfo.SeparationDate -Ticket $ticket -name $employeeInfo.FullName
            
        $ticketsToProcess += $ticketInfo
    }
    
    return $ticketsToProcess
}


# Function to get and validate Jira API Key from environment variable
function Get-JiraAPIKey {
    # Define the environment variable name
    $envVariableName = "JIRA_API_KEY"

    # Check if environment variable exists
    $JiraAPIKey = [Environment]::GetEnvironmentVariable($envVariableName, "Machine")
    # if no API key display instructions to get a key
    if ([string]::IsNullOrWhiteSpace($JiraAPIKey)) {
        throw "Jira API Key environment variable not set"
        exit
    }
    
    return $JiraAPIKey
}

$JiraAPIKey = Get-JiraAPIKey
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(
        "$($JiraEmail):$($JiraAPIKey)"))


function Resolve-Ticket {
    param (
        [Parameter(Mandatory=$true)]
        [object]$ticket,
        [Parameter(Mandatory=$true)]
        [string]$accountUsername,
        [Parameter(Mandatory=$true)]
        [string]$separationDate
    )
    
    $headers = @{
        "Authorization" = "Basic $base64AuthInfo"
        "Content-Type" = "application/json"
    }
    
    $ticketID = $ticket.Key
    
    # Retrieve the ticket details to get the submitter's name
    $ticketDetailsUri = "$jiraBaseURL/rest/api/2/issue/$ticketID"
    
    try {
        # Fetch ticket details to get submitter information
        $ticketDetails = Invoke-RestMethod -Uri $ticketDetailsUri -Method Get -Headers $headers
        
        # Extract submitter's display name (or use email if display name is not available)
        $submitterName = $ticketDetails.fields.creator.displayName
        if ([string]::IsNullOrWhiteSpace($submitterName)) {
            $submitterName = $ticketDetails.fields.creator.emailAddress
        }
        $firstName = $submitterName.Split(' ')[0]
        $formattedSeparationDate = $separationDate
        
        $commentBody = @{
            "body" = @"
Hi $firstName,

The account $accountUsername has been set to be disabled on $formattedSeparationDate.

Thank you,
Jonathan Allen
"@
        } | ConvertTo-Json

        # 1. Add the comment
        $commentUri = "$jiraBaseURL/rest/api/2/issue/$ticketID/comment"
        $commentResponse = Invoke-RestMethod -Uri $commentUri -Method POST -Headers $headers -Body $commentBody

        # ID of 761 means resolved
        $transitionBody = @{
            "transition" = @{
                "id" = "761"
            }
        } | ConvertTo-Json -Depth 4

        $transitionUri = "$jiraBaseURL/rest/api/2/issue/$ticketID/transitions"
        $transitionResponse = Invoke-RestMethod -Uri $transitionUri -Method POST -Headers $headers -Body $transitionBody

        Write-Output "Successfully added comment and transitioned ticket $ticketID to Resolved status."
        return $true
    }
    catch {
        Write-Error "Failed to resolve $ticketID. Error: $_"      
        return $false
    }
}

function Find-JiraTickets {
    param(
        [string]$SearchTitle,
        [string]$BaseUrl,
        [string]$Base64Auth,
        [string]$ProjectKey = "ITS",
        [int]$MaxResults = 100  # Increased to fetch more results
    )
    
    # JQL query to find open tickets matching the title
    $jqlQuery = "project = $ProjectKey AND summary ~ `"$SearchTitle`" AND status != Resolved ORDER BY created DESC"
    $encodedJql = [System.Web.HttpUtility]::UrlEncode($jqlQuery)
    $searchUrl = "$BaseUrl/rest/api/3/search?jql=$encodedJql&maxResults=$MaxResults"
    
    $headers = @{
        "Authorization" = "Basic $Base64Auth"
        "Content-Type" = "application/json"
    }
    
    try {
        Write-Host "Searching for open tickets with title: $SearchTitle" -ForegroundColor Cyan
        Write-Host "Using URL: $searchUrl" -ForegroundColor Gray
        
        $response = Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method Get
        
        if ($response.issues -and $response.issues.Count -gt 0) {
            $ticketList = @()
            
            foreach ($ticket in $response.issues) {
                Write-Host "Found ticket: $($ticket.key) - $($ticket.fields.summary)" -ForegroundColor Green
                $ticketList += [PSCustomObject]@{
                    Key = $ticket.key
                    Summary = $ticket.fields.summary
                    Description = $ticket.fields.description
                }
            }
            
            Write-Host "Total tickets found: $($ticketList.Count)" -ForegroundColor Green
            return $ticketList
        } else {
            Write-Host "No open tickets found matching title '$SearchTitle' in project $ProjectKey" -ForegroundColor Yellow
            return @()
        }
    } catch {
        Write-Host "Error searching Jira: $_" -ForegroundColor Red
        if ($_.Exception.Response) {
            $responseBody = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($responseBody)
            $responseContent = $reader.ReadToEnd()
            Write-Host "Response content: $responseContent" -ForegroundColor Red
        }
        return @()  # Return empty array instead of exiting
    }
}

function Deactivate-User {
    param (
        [Parameter(Mandatory = $true)]
        [string]$SNum,
        [Parameter(Mandatory = $true)]
        [DateTime]$SeparationDate,
        [Parameter(Mandatory=$true)]
        [object]$Ticket,
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    # Import the ActiveDirectory module if not already loaded
    if (-not (Get-Module -Name ActiveDirectory)) {
        Import-Module ActiveDirectory
    }

    try {
        $s0User = Get-ADUser -Filter {
            SamAccountName -eq $SNum
        } -Properties Description, Title
        if($s0User){
            $username = $s0User.Name
            $w0User = Get-ADUser -Filter {
            Name -eq $username -and SamAccountName -like 'W0*'
        } -Properties Description, Title
        }
        else{
            # if we can't use the provided S num then try to use their name
            $nameParts = $name.Trim().Split(' ', 2)
            $firstName = $nameParts[0]
            $lastName = $nameParts[1]
            $convertedName = "$lastName, $firstName"
            $w0User = Get-ADUser -Filter {
            Name -eq $convertedName -and SamAccountName -like 'W0*'
            }
            $s0User = Get-ADUser -Filter {
            Name -eq $convertedName -and SamAccountName -like 'S0*'
            }
            }
        
        # Function to update user description
        function Update-UserDescription {
            param(
                [Parameter(Mandatory = $true)]
                [Microsoft.ActiveDirectory.Management.ADUser]$User,
                [Parameter(Mandatory = $true)]
                [string]$TicketKey
            )

            $newDescription = "Disabled Per ITS - $TicketKey"
            Set-ADUser -Identity $User -Description $newDescription
            Write-Host "Updated description for $($User.SamAccountName) to: $newDescription" -ForegroundColor Green
        }

        # If W0 user found, update and disable it
        if ($w0User) {
            # Update description
            Update-UserDescription -User $w0User -TicketKey $Ticket.Key
            Set-ADUser -Identity $w0User -AccountExpirationDate $SeparationDate -ErrorAction Stop
            Write-Host "Account '$($w0User.SamAccountName)' expiration date set to $($SeparationDate.ToShortDateString())."
            Resolve-Ticket -ticket $Ticket -accountUsername $name -separationDate $SeparationDate
            return
        }
        
        if ($s0User) {
            Update-UserDescription -User $s0User -TicketKey $Ticket.Key
            Set-ADUser -Identity $s0User -AccountExpirationDate $SeparationDate -ErrorAction Stop
            Write-Host "Account '$($s0User.SamAccountName)' expiration date set to $($SeparationDate.ToShortDateString())."
            
            Resolve-Ticket -ticket $Ticket -accountUsername $name -separationDate $SeparationDate
        } else {
            Write-Host "No matching user found with S# '$s0User."
        }
    }
    catch {
        Write-Error "An error occurred: $_"
    }
}

# Load the System.Web assembly for URL encoding
Add-Type -AssemblyName System.Web

$searchTitle = "Cancel Access After"
Write-Host "Searching for open tickets with title similar to: $searchTitle"
$ticketIds = Find-JiraTickets -SearchTitle $searchTitle -BaseUrl $jiraBaseUrl -Base64Auth $base64AuthInfo
$ticketsToProcess = EmployeeTickets -Tickets $ticketIds
