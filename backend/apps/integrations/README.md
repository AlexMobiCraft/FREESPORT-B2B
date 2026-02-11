# Integrations App

This app handles external integrations for FREESPORT, including 1C:Enterprise, Payment Gateways, and Delivery Services.

## 1C Exchange Internal Module (`onec_exchange`)

Handles the HTTP exchange protocol with 1C:Enterprise (CommerceML).

### Debugging with CURL

You can test the exchange flow manually using `curl`.

**1. Authenticate (CheckAuth)**
```bash
# Returns session cookie and success status
curl -v -u <1c_username>:<password> "http://localhost:8001/api/integration/1c/exchange/?mode=checkauth"
```
*Response:*
```
success
FREESPORT_1C_SESSION
<session_id>
```

**2. Initialize (Init)**
```bash
# Negotiate parameters (zip, limit)
curl -v -H "Cookie: FREESPORT_1C_SESSION=<session_id>" "http://localhost:8001/api/integration/1c/exchange/?mode=init"
```

**3. Upload File (File)**
```bash
# Upload a test file (e.g. goods.xml)
curl -v -X POST \
     -H "Cookie: FREESPORT_1C_SESSION=<session_id>" \
     --data-binary @path/to/local/goods.xml \
     "http://localhost:8001/api/integration/1c/exchange/?mode=file&filename=goods.xml&sessid=<session_id>"
```

**4. Trigger Import (Import)**
```bash
# Signal that upload is complete
curl -v -H "Cookie: FREESPORT_1C_SESSION=<session_id>" "http://localhost:8001/api/integration/1c/exchange/?mode=import&filename=goods.xml&sessid=<session_id>"
```

### Permissions

Users must have the `integrations.can_exchange_1c` permission to access these endpoints. The `admin` role has this by default.
