param(
    [string]$BaseUrl = "https://mainspring.au",
    [string]$TenantSlug = "pilotshop",
    [string]$OwnerEmail = "owner@pilotshop.au",
    [string]$OwnerPassword = "pilotpass123",
    [switch]$SkipSignup,
    [string]$StatusToken = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Assert-True($condition, $message) {
    if (-not $condition) {
        throw $message
    }
}

function Invoke-JsonPost($uri, $payload) {
    $json = $payload | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body $json
}

Write-Step "Health check"
$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/v1/health"
Assert-True ($health.status -eq "ok") "Health endpoint did not return status=ok"
Write-Host "Health OK"

if (-not $SkipSignup) {
    Write-Step "Signup endpoint"
    $signupPayload = @{
        tenant_name = "Pilot Shop"
        tenant_slug = $TenantSlug
        email = $OwnerEmail
        full_name = "Pilot Owner"
        password = $OwnerPassword
    }

    try {
        $signup = Invoke-JsonPost "$BaseUrl/v1/auth/signup" $signupPayload
        Assert-True ([string]::IsNullOrWhiteSpace($signup.access_token) -eq $false) "Signup did not return access_token"
        Write-Host "Signup OK"
    }
    catch {
        Write-Warning "Signup failed or may already exist: $($_.Exception.Message)"
    }
}

Write-Step "Login endpoint"
$loginPayload = @{
    tenant_slug = $TenantSlug
    email = $OwnerEmail
    password = $OwnerPassword
}
$login = Invoke-JsonPost "$BaseUrl/v1/auth/login" $loginPayload
Assert-True ([string]::IsNullOrWhiteSpace($login.access_token) -eq $false) "Login did not return access_token"
Write-Host "Login OK"

if (-not [string]::IsNullOrWhiteSpace($StatusToken)) {
    Write-Step "Public status page and QR endpoint"

    $statusPage = Invoke-WebRequest -Method Get -Uri "$BaseUrl/status/$StatusToken"
    Assert-True ($statusPage.StatusCode -ge 200 -and $statusPage.StatusCode -lt 400) "Status page request failed"

    $qr = Invoke-WebRequest -Method Get -Uri "$BaseUrl/v1/public/jobs/$StatusToken/qr"
    Assert-True ($qr.StatusCode -eq 200) "QR endpoint did not return HTTP 200"

    Write-Host "Public status and QR OK"
}
else {
    Write-Host "Skipping status/QR checks (pass -StatusToken to enable)" -ForegroundColor Yellow
}

Write-Step "Completed"
Write-Host "Mainspring smoke test passed for $BaseUrl" -ForegroundColor Green
