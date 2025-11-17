# Remote Account Management Guide

This guide shows how to add accounts to the XOAUTH2 Proxy from **other apps or servers** using the HTTP Admin API.

---

## 🌐 Server Setup

The Admin API now binds to **0.0.0.0** by default (accessible from internet).

### Start the Proxy

```bash
# Default - Admin API accessible from internet on port 9090
python xoauth2_proxy_v2.py

# Custom port
python xoauth2_proxy_v2.py --admin-port 8080

# Restrict to localhost only (if needed)
python xoauth2_proxy_v2.py --admin-host 127.0.0.1
```

### Find Your Server IP

```bash
# Public IP
curl ifconfig.me

# Private IP
ip addr show | grep inet
# Or: hostname -I
```

**Example:** Your server IP is `203.0.113.50`
**Admin API URL:** `http://203.0.113.50:9090`

---

## 🔐 Security Recommendations

### Option 1: Firewall Rules (Recommended)

```bash
# Allow only from specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 9090 proto tcp
sudo ufw allow from 10.0.0.5 to any port 9090 proto tcp

# Check rules
sudo ufw status
```

### Option 2: Reverse Proxy with Authentication

Use nginx with basic auth:

```nginx
server {
    listen 443 ssl;
    server_name admin.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        auth_basic "Admin Area";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 3: VPN/SSH Tunnel

```bash
# SSH tunnel from remote server
ssh -L 9090:localhost:9090 user@proxy-server

# Then access via localhost
curl http://localhost:9090/admin/accounts
```

---

## 📡 API Endpoint

**Base URL:** `http://YOUR_SERVER_IP:9090`

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/admin/accounts` | List all accounts |
| POST | `/admin/accounts` | Add new account |

---

## 🚀 Add Account from Different Apps/Languages

### 1️⃣ Python (requests)

```python
import requests

# Your proxy server
PROXY_URL = "http://203.0.113.50:9090"

def add_account(email, provider, client_id, client_secret, refresh_token):
    """Add account to XOAUTH2 proxy"""

    data = {
        "email": email,
        "provider": provider,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "verify": True  # Verify credentials before saving
    }

    response = requests.post(
        f"{PROXY_URL}/admin/accounts",
        json=data,
        timeout=30
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ {result['message']}")
        print(f"Total accounts: {result['total_accounts']}")
        return True
    else:
        error = response.json()
        print(f"✗ Error: {error['error']}")
        return False

# Example usage
add_account(
    email="sales@gmail.com",
    provider="gmail",
    client_id="123456789-abc.apps.googleusercontent.com",
    client_secret="GOCSPX-abc123def456",
    refresh_token="1//0gABC123DEF456..."
)
```

### 2️⃣ Python (aiohttp - Async)

```python
import aiohttp
import asyncio

PROXY_URL = "http://203.0.113.50:9090"

async def add_account_async(email, provider, client_id, client_secret, refresh_token):
    """Add account asynchronously"""

    data = {
        "email": email,
        "provider": provider,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "verify": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{PROXY_URL}/admin/accounts",
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            result = await response.json()

            if response.status == 200:
                print(f"✓ {result['message']}")
                return True
            else:
                print(f"✗ Error: {result['error']}")
                return False

# Run
asyncio.run(add_account_async(
    email="sales@gmail.com",
    provider="gmail",
    client_id="123456789-abc.apps.googleusercontent.com",
    client_secret="GOCSPX-abc123def456",
    refresh_token="1//0gABC123DEF456..."
))
```

### 3️⃣ PHP

```php
<?php
$proxyUrl = "http://203.0.113.50:9090";

function addAccount($email, $provider, $clientId, $clientSecret, $refreshToken) {
    global $proxyUrl;

    $data = array(
        'email' => $email,
        'provider' => $provider,
        'client_id' => $clientId,
        'client_secret' => $clientSecret,
        'refresh_token' => $refreshToken,
        'verify' => true
    );

    $options = array(
        'http' => array(
            'header'  => "Content-type: application/json\r\n",
            'method'  => 'POST',
            'content' => json_encode($data),
            'timeout' => 30
        )
    );

    $context  = stream_context_create($options);
    $result = file_get_contents($proxyUrl . '/admin/accounts', false, $context);

    if ($result === FALSE) {
        echo "✗ Failed to add account\n";
        return false;
    }

    $response = json_decode($result, true);

    if ($response['success']) {
        echo "✓ " . $response['message'] . "\n";
        echo "Total accounts: " . $response['total_accounts'] . "\n";
        return true;
    } else {
        echo "✗ Error: " . $response['error'] . "\n";
        return false;
    }
}

// Example usage
addAccount(
    "sales@gmail.com",
    "gmail",
    "123456789-abc.apps.googleusercontent.com",
    "GOCSPX-abc123def456",
    "1//0gABC123DEF456..."
);
?>
```

### 4️⃣ Node.js (JavaScript)

```javascript
const axios = require('axios');

const PROXY_URL = 'http://203.0.113.50:9090';

async function addAccount(email, provider, clientId, clientSecret, refreshToken) {
    try {
        const response = await axios.post(`${PROXY_URL}/admin/accounts`, {
            email: email,
            provider: provider,
            client_id: clientId,
            client_secret: clientSecret,
            refresh_token: refreshToken,
            verify: true
        }, {
            timeout: 30000
        });

        if (response.data.success) {
            console.log(`✓ ${response.data.message}`);
            console.log(`Total accounts: ${response.data.total_accounts}`);
            return true;
        }
    } catch (error) {
        if (error.response) {
            console.log(`✗ Error: ${error.response.data.error}`);
        } else {
            console.log(`✗ Error: ${error.message}`);
        }
        return false;
    }
}

// Example usage
addAccount(
    'sales@gmail.com',
    'gmail',
    '123456789-abc.apps.googleusercontent.com',
    'GOCSPX-abc123def456',
    '1//0gABC123DEF456...'
);
```

### 5️⃣ C# (.NET)

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

class ProxyAccountManager
{
    private static readonly string PROXY_URL = "http://203.0.113.50:9090";
    private static readonly HttpClient client = new HttpClient();

    public static async Task<bool> AddAccount(
        string email,
        string provider,
        string clientId,
        string clientSecret,
        string refreshToken)
    {
        var data = new
        {
            email = email,
            provider = provider,
            client_id = clientId,
            client_secret = clientSecret,
            refresh_token = refreshToken,
            verify = true
        };

        var json = JsonSerializer.Serialize(data);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        try
        {
            var response = await client.PostAsync($"{PROXY_URL}/admin/accounts", content);
            var responseBody = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<JsonElement>(responseBody);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine($"✓ {result.GetProperty("message").GetString()}");
                Console.WriteLine($"Total accounts: {result.GetProperty("total_accounts").GetInt32()}");
                return true;
            }
            else
            {
                Console.WriteLine($"✗ Error: {result.GetProperty("error").GetString()}");
                return false;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"✗ Error: {ex.Message}");
            return false;
        }
    }

    static async Task Main(string[] args)
    {
        await AddAccount(
            "sales@gmail.com",
            "gmail",
            "123456789-abc.apps.googleusercontent.com",
            "GOCSPX-abc123def456",
            "1//0gABC123DEF456..."
        );
    }
}
```

### 6️⃣ Go (Golang)

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
    "time"
)

const PROXY_URL = "http://203.0.113.50:9090"

type AccountRequest struct {
    Email         string `json:"email"`
    Provider      string `json:"provider"`
    ClientID      string `json:"client_id"`
    ClientSecret  string `json:"client_secret"`
    RefreshToken  string `json:"refresh_token"`
    Verify        bool   `json:"verify"`
}

type AccountResponse struct {
    Success       bool   `json:"success"`
    Message       string `json:"message"`
    TotalAccounts int    `json:"total_accounts"`
    Error         string `json:"error"`
}

func addAccount(email, provider, clientID, clientSecret, refreshToken string) error {
    data := AccountRequest{
        Email:        email,
        Provider:     provider,
        ClientID:     clientID,
        ClientSecret: clientSecret,
        RefreshToken: refreshToken,
        Verify:       true,
    }

    jsonData, err := json.Marshal(data)
    if err != nil {
        return err
    }

    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Post(
        PROXY_URL+"/admin/accounts",
        "application/json",
        bytes.NewBuffer(jsonData),
    )
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    body, err := ioutil.ReadAll(resp.Body)
    if err != nil {
        return err
    }

    var result AccountResponse
    err = json.Unmarshal(body, &result)
    if err != nil {
        return err
    }

    if result.Success {
        fmt.Printf("✓ %s\n", result.Message)
        fmt.Printf("Total accounts: %d\n", result.TotalAccounts)
        return nil
    } else {
        return fmt.Errorf("✗ Error: %s", result.Error)
    }
}

func main() {
    err := addAccount(
        "sales@gmail.com",
        "gmail",
        "123456789-abc.apps.googleusercontent.com",
        "GOCSPX-abc123def456",
        "1//0gABC123DEF456...",
    )

    if err != nil {
        fmt.Println(err)
    }
}
```

### 7️⃣ Ruby

```ruby
require 'net/http'
require 'json'
require 'uri'

PROXY_URL = 'http://203.0.113.50:9090'

def add_account(email, provider, client_id, client_secret, refresh_token)
  uri = URI("#{PROXY_URL}/admin/accounts")

  data = {
    email: email,
    provider: provider,
    client_id: client_id,
    client_secret: client_secret,
    refresh_token: refresh_token,
    verify: true
  }

  http = Net::HTTP.new(uri.host, uri.port)
  http.read_timeout = 30

  request = Net::HTTP::Post.new(uri.path, 'Content-Type' => 'application/json')
  request.body = data.to_json

  response = http.request(request)
  result = JSON.parse(response.body)

  if result['success']
    puts "✓ #{result['message']}"
    puts "Total accounts: #{result['total_accounts']}"
    true
  else
    puts "✗ Error: #{result['error']}"
    false
  end
rescue => e
  puts "✗ Error: #{e.message}"
  false
end

# Example usage
add_account(
  'sales@gmail.com',
  'gmail',
  '123456789-abc.apps.googleusercontent.com',
  'GOCSPX-abc123def456',
  '1//0gABC123DEF456...'
)
```

### 8️⃣ Bash/cURL (Shell Script)

```bash
#!/bin/bash

PROXY_URL="http://203.0.113.50:9090"

add_account() {
    local email="$1"
    local provider="$2"
    local client_id="$3"
    local client_secret="$4"
    local refresh_token="$5"

    response=$(curl -s -w "\n%{http_code}" -X POST "${PROXY_URL}/admin/accounts" \
        -H "Content-Type: application/json" \
        -d "{
            \"email\": \"${email}\",
            \"provider\": \"${provider}\",
            \"client_id\": \"${client_id}\",
            \"client_secret\": \"${client_secret}\",
            \"refresh_token\": \"${refresh_token}\",
            \"verify\": true
        }" \
        --max-time 30)

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        message=$(echo "$body" | jq -r '.message')
        total=$(echo "$body" | jq -r '.total_accounts')
        echo "✓ $message"
        echo "Total accounts: $total"
        return 0
    else
        error=$(echo "$body" | jq -r '.error')
        echo "✗ Error: $error"
        return 1
    fi
}

# Example usage
add_account \
    "sales@gmail.com" \
    "gmail" \
    "123456789-abc.apps.googleusercontent.com" \
    "GOCSPX-abc123def456" \
    "1//0gABC123DEF456..."
```

### 9️⃣ PowerShell (Windows)

```powershell
$ProxyUrl = "http://203.0.113.50:9090"

function Add-Account {
    param(
        [string]$Email,
        [string]$Provider,
        [string]$ClientId,
        [string]$ClientSecret,
        [string]$RefreshToken
    )

    $body = @{
        email = $Email
        provider = $Provider
        client_id = $ClientId
        client_secret = $ClientSecret
        refresh_token = $RefreshToken
        verify = $true
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod `
            -Uri "$ProxyUrl/admin/accounts" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 30

        if ($response.success) {
            Write-Host "✓ $($response.message)" -ForegroundColor Green
            Write-Host "Total accounts: $($response.total_accounts)"
            return $true
        }
    }
    catch {
        $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "✗ Error: $($errorResponse.error)" -ForegroundColor Red
        return $false
    }
}

# Example usage
Add-Account `
    -Email "sales@gmail.com" `
    -Provider "gmail" `
    -ClientId "123456789-abc.apps.googleusercontent.com" `
    -ClientSecret "GOCSPX-abc123def456" `
    -RefreshToken "1//0gABC123DEF456..."
```

### 🔟 Java

```java
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.json.JSONObject;

public class ProxyAccountManager {
    private static final String PROXY_URL = "http://203.0.113.50:9090";

    public static boolean addAccount(
        String email,
        String provider,
        String clientId,
        String clientSecret,
        String refreshToken
    ) {
        JSONObject data = new JSONObject();
        data.put("email", email);
        data.put("provider", provider);
        data.put("client_id", clientId);
        data.put("client_secret", clientSecret);
        data.put("refresh_token", refreshToken);
        data.put("verify", true);

        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(PROXY_URL + "/admin/accounts"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(data.toString()))
            .build();

        try {
            HttpResponse<String> response = client.send(
                request,
                HttpResponse.BodyHandlers.ofString()
            );

            JSONObject result = new JSONObject(response.body());

            if (result.getBoolean("success")) {
                System.out.println("✓ " + result.getString("message"));
                System.out.println("Total accounts: " + result.getInt("total_accounts"));
                return true;
            } else {
                System.out.println("✗ Error: " + result.getString("error"));
                return false;
            }
        } catch (IOException | InterruptedException e) {
            System.out.println("✗ Error: " + e.getMessage());
            return false;
        }
    }

    public static void main(String[] args) {
        addAccount(
            "sales@gmail.com",
            "gmail",
            "123456789-abc.apps.googleusercontent.com",
            "GOCSPX-abc123def456",
            "1//0gABC123DEF456..."
        );
    }
}
```

---

## 📊 Response Examples

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Account sales@gmail.com added successfully",
  "total_accounts": 5,
  "account": {
    "email": "sales@gmail.com",
    "provider": "gmail",
    "oauth_endpoint": "smtp.gmail.com:587"
  }
}
```

### Error Responses

**Missing Fields (400)**
```json
{
  "success": false,
  "error": "Missing required fields: client_secret, refresh_token"
}
```

**Invalid Email (400)**
```json
{
  "success": false,
  "error": "Invalid email format"
}
```

**OAuth2 Verification Failed (400)**
```json
{
  "success": false,
  "error": "OAuth2 verification failed: invalid_grant - Token has been expired or revoked"
}
```

**Duplicate Account (409)**
```json
{
  "success": false,
  "error": "Account sales@gmail.com already exists. Use \"overwrite\": true to replace it."
}
```

---

## 🔄 Bulk Account Import

### Python Script for Bulk Import

```python
import requests
import csv

PROXY_URL = "http://203.0.113.50:9090"

def import_accounts_from_csv(csv_file):
    """Import accounts from CSV file"""

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)

        success_count = 0
        error_count = 0

        for row in reader:
            data = {
                "email": row['email'],
                "provider": row['provider'],
                "client_id": row['client_id'],
                "client_secret": row.get('client_secret', ''),
                "refresh_token": row['refresh_token'],
                "verify": True
            }

            response = requests.post(f"{PROXY_URL}/admin/accounts", json=data)

            if response.status_code == 200:
                print(f"✓ Added: {row['email']}")
                success_count += 1
            else:
                error = response.json().get('error', 'Unknown error')
                print(f"✗ Failed: {row['email']} - {error}")
                error_count += 1

        print(f"\n✓ Success: {success_count}")
        print(f"✗ Failed: {error_count}")

# CSV format:
# email,provider,client_id,client_secret,refresh_token
# sales@gmail.com,gmail,123-abc.apps.googleusercontent.com,GOCSPX-abc,1//0gABC...
# support@outlook.com,outlook,456-def,secret,M.R3_BAY...

import_accounts_from_csv('accounts.csv')
```

---

## 🧪 Testing from Remote Server

```bash
# From another server, test connectivity
curl http://203.0.113.50:9090/health

# Expected response:
# {"status": "healthy", "service": "xoauth2-proxy-admin"}

# List accounts
curl http://203.0.113.50:9090/admin/accounts

# Add account
curl -X POST http://203.0.113.50:9090/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@gmail.com",
    "provider": "gmail",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "verify": false
  }'
```

---

## 📝 Best Practices

1. **Always verify credentials** - Use `"verify": true` to catch OAuth2 errors early
2. **Handle errors gracefully** - Check HTTP status codes and error messages
3. **Use timeouts** - Set reasonable timeouts (30 seconds recommended)
4. **Secure credentials** - Never log or expose OAuth2 tokens
5. **Use HTTPS** - In production, use reverse proxy with SSL/TLS
6. **Implement retry logic** - For transient network errors
7. **Rate limiting** - Don't flood the API with requests

---

## 🛡️ Security Checklist

- [ ] Firewall configured to allow only trusted IPs
- [ ] Using HTTPS (via reverse proxy)
- [ ] Authentication enabled (basic auth or API key)
- [ ] Regular security updates
- [ ] Monitoring API access logs
- [ ] accounts.json has restricted permissions (chmod 600)

---

## 📞 Support

For more information:
- API Reference: `docs/ADMIN_API.md`
- Account Setup: `SETUP_ACCOUNTS.md`
- Quick Start: `QUICK_START.md`
