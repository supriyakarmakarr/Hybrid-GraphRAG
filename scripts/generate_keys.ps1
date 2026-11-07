# Generate 2048-bit RSA Keypair using .NET standard libraries
New-Item -ItemType Directory -Force -Path 'keys' | Out-Null

$rsa = [System.Security.Cryptography.RSA]::Create(2048)
$privBytes = $rsa.ExportPkcs8PrivateKey()
$pubBytes = $rsa.ExportSubjectPublicKeyInfo()

$privB64 = [System.Convert]::ToBase64String($privBytes, [System.Base64FormattingOptions]::InsertLineBreaks)
$pubB64 = [System.Convert]::ToBase64String($pubBytes, [System.Base64FormattingOptions]::InsertLineBreaks)

$privPem = "-----BEGIN PRIVATE KEY-----`r`n" + $privB64 + "`r`n-----END PRIVATE KEY-----`r`n"
$pubPem = "-----BEGIN PUBLIC KEY-----`r`n" + $pubB64 + "`r`n-----END PUBLIC KEY-----`r`n"

[System.IO.File]::WriteAllText("keys/private.pem", $privPem)
[System.IO.File]::WriteAllText("keys/public.pem", $pubPem)

Write-Host "RSA keys generated successfully in keys/ directory."
Write-Host "Private: keys/private.pem"
Write-Host "Public:  keys/public.pem"

