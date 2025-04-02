# Jira Ticket Creation Script

function Set-JiraAPIKeyEnvironmentVariable {
    # Define the environment variable name
    $envVariableName = "JIRA_API_KEY"

    # Check if environment variable already exists
    $existingAPIKey = [Environment]::GetEnvironmentVariable($envVariableName, "User")

    if ([string]::IsNullOrWhiteSpace($existingAPIKey)) {
        Write-Host "No Jira API Key found in environment variables."
        Write-Host "Please follow these steps:"
        Write-Host "1. Go to Jira Account Settings"
        Write-Host "2. Generate an API Token"
        Write-Host "3. Run the following command in PowerShell as Administrator:"
        Write-Host "`$env:JIRA_API_KEY = 'YOUR_API_KEY_HERE'"
        Write-Host "4. To make it permanent, use:"
        Write-Host "[Environment]::SetEnvironmentVariable('JIRA_API_KEY', 'YOUR_API_KEY_HERE', 'User')"
        
        throw "Jira API Key environment variable not set"
    }
}
    # Validate Jira API Key is set
    Set-JiraAPIKeyEnvironmentVariable
    function New-JiraTicket {
        # macd is 127
        param (
            [Parameter(Mandatory=$true)]
            [string]$Subject,
            
            [Parameter(Mandatory=$false)]
            [string]$Description = "Automated ticket for new account creation", # Placeholder decription
            
            [string]$AssigneeUsername = "1f450727-b053-4bea-95cc-cd50e3a74f95", # Jonathan's username
            
            [string]$CsvFilePath = "C:\Users\W02814770\Scripts\RRCCNewHires.csv", # replace with actual file path to CSV
            
            [string]$JiraServerUrl = "https://redrockscommunitycollege.atlassian.net/", # our JIRA URL
            
            [string]$ProjectKey = "ITS", # add to the ITS project
    
            [string]$JiraUsername = "joseph.work@rrcc.edu" # replace with jira username that matches API key
        )
    
        # Validate Jira API Key is set
        $JiraAPIToken = [Environment]::GetEnvironmentVariable("JIRA_API_KEY", "User")
        if ([string]::IsNullOrWhiteSpace($JiraAPIToken)) {
            Write-Host "Error: Jira API Key not set"
            Write-Host "Please set the environment variable JIRA_API_KEY:"
            Write-Host "[Environment]::SetEnvironmentVariable('JIRA_API_KEY', 'your-api-token', 'User')"
            return $null
        }
    
        # Prepare API Authentication
        $base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(
            "$($JiraUsername):$($JiraAPIToken)"))
    
        # Prepare Headers
        $headers = @{
            "Authorization" = "Basic $base64AuthInfo"
            "Content-Type" = "application/json"
        }
    
        # Ticket Creation Payload
        $ticketPayload = @{
            fields = @{
                project = @{
                    key = $ProjectKey
                }
                summary = $Subject
                description = @{
                    type = "doc"
                    version = 1
                    content = @(
                        @{
                            type = "paragraph"
                            content = @(
                                @{
                                    type = "text"
                                    text = $Description
                                }
                            )
                        }
                    )
                }
                issuetype = @{
                    id = "10005"        # [System] Service Request ID 
                }
                assignee = @{
                    accountId = "712020:1f450727-b053-4bea-95cc-cd50e3a74f95" # Jonathan's account ID
                }
                customfield_10010 = "127"  # MACD request type ID
                
            }
        } | ConvertTo-Json -Depth 10
    
        try {
            # Create Ticket
            $ticketResponse = Invoke-RestMethod -Uri "$JiraServerUrl/rest/api/3/issue" `
                -Method Post `
                -Headers $headers `
                -Body $ticketPayload
            $issueKey = $ticketResponse.key
    
            # Attach CSV File if it Exists
            if (Test-Path $CsvFilePath) {
                $attachmentPath = $CsvFilePath
    
                # Headers for attachment
                $headers = @{
                    "Authorization" = "Basic $base64AuthInfo"
                    "X-Atlassian-Token" = "no-check"  # Required to bypass CSRF check
                    "Content-Type" = "multipart/form-data; boundary=$boundary"
                }
    
                # Read file content
                    $fileBytes = [System.IO.File]::ReadAllBytes($attachmentPath)
                    $fileEnc = [System.Text.Encoding]::GetEncoding("ISO-8859-1").GetString($fileBytes)

                    # Create multipart/form-data body
                    $boundary = [System.Guid]::NewGuid().ToString()
                    $LF = "`r`n"
                    $bodyLines = (
                        "--$boundary",
                        "Content-Disposition: form-data; name=`"file`"; filename=`"$([System.IO.Path]::GetFileName($attachmentPath))`"",
                        "Content-Type: application/octet-stream$LF",
                        $fileEnc,
                        "--$boundary--$LF"
                    )
                    $body = $bodyLines -join $LF

                    # Invoke REST method
                    Invoke-RestMethod -Uri "$jiraServerUrl/rest/api/2/issue/$issueKey/attachments" -Method Post -Headers $headers -ContentType "multipart/form-data; boundary=$boundary" -Body $body
            } else {
                Write-Warning "File not found at $CsvFilePath"
            }
    
            Write-Host "Ticket created successfully with key: $issueKey"
            return $issueKey
        } catch {
            Write-Error "Failed to create Jira ticket or attach file: $_"
            if ($_.Exception.Response) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $reader.BaseStream.Position = 0
                $reader.DiscardBufferedData()
                $responseBody = $reader.ReadToEnd()
                Write-Error "Detailed Error Response: $responseBody"
            }
            return $null
        }
    }

# Interactive Ticket Creation
Write-Host "Jira Ticket Creation Utility"
Write-Host "============================="

# Prompt user for ticket subject
$ticketSubject = Read-Host "Please enter the subject for the Jira ticket"
$ticketDescription = Read-Host "Please enter the description for the Jira ticket"

# Validate input
if ([string]::IsNullOrWhiteSpace($ticketSubject)) {
    Write-Host "Error: Ticket subject cannot be empty"
    exit
}

# Create the ticket with user-provided subject
New-JiraTicket -Subject $ticketSubject $ticketDescription
