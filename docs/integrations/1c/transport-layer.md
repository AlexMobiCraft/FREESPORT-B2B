# Technical Specification: 1C Transport Layer

**Version:** 1.0
**Status:** Implemented (Epics 1 & 2)
**Related Architecture:** [Architecture Overview](architecture.md)

---

## 1. Overview

The Transport Layer acts as the bridge between 1C:Enterprise and the FREESPORT platform. It implements the standard "1C-Bitrix Site Exchange" protocol via HTTP(S).

**Key Responsibilities:**
- Establishing a secure session with 1C.
- Negotiating transfer parameters (compression, file limits).
- Receiving large data archives via chunked uploads.
- Routing files to the appropriate import queues.

## 2. Authentication

The system uses a hybrid authentication mechanism required by the 1C protocol:

1.  **Initial Handshake:** Basic Authentication.
2.  **Session Maintenance:** Standard Django Session Cookie.

> **Security Note:** The exchange endpoints (`/api/integration/1c/exchange/`) are **CSRF Exempt** (see [ADR-009](../../decisions/ADR-009-csrf-exemption-1c-protocol.md)) because 1C does not support CSRF token exchange. Security is maintained via:
> - Strict Origin checks (if applicable).
> - Session IP binding (optional future enhancement).
> - Restricted user permissions (`can_exchange_1c`).

## 3. Protocol Endpoints

**Base URL:** `/api/integration/1c/exchange/`

### 3.1 Step 1: Checkauth

Initializes the session.

- **Request:** `GET ?mode=checkauth`
- **Headers:** `Authorization: Basic <base64 credentials>`
- **Response (Success):** `200 OK`, `Content-Type: text/plain`
  ```text
  success
  FREESPORT_1C_SESSION
  <session_id_value>
  ```
- **Response (Failure):** `401 Unauthorized`

### 3.2 Step 2: Init

Negotiates capabilities.

- **Request:** `GET ?mode=init`
- **Headers:** `Cookie: FREESPORT_1C_SESSION=<value>`
- **Response:** `200 OK`, `Content-Type: text/plain`
  ```text
  zip=yes
  file_limit=104857600
  sessid=<session_id_value>
  version=3.1
  ```
  *(Note: `file_limit` is set to 100MB per chunk)*

### 3.3 Step 3: File Upload

Transfers data chunks.

- **Request:** `POST ?mode=file&filename=<name>&sessid=<id>`
- **Body:** Binary content (chunk data)
- **Response:** `200 OK`, `Content-Type: text/plain`
  - `success`
  - OR `failure\n<Error Message>`

**Logic:**
- Chunks for the same `filename` are appended sequentially.
- Files are stored in a temporary isolation directory: `MEDIA_ROOT/1c_temp/<session_id>/`.
- **ZIP Archives:** Stored as-is, not unpacked at this stage.

### 3.4 Step 4: Import (Routing)

Signals that upload is complete and triggers transfer/unpack into the import queue.

- **Request:** `GET ?mode=import&filename=<name>&sessid=<id>`
- **Response:**
  - `success` (if processing started/queued)
  - `failure`

**Routing Logic (`FileRoutingService`):**
1.  **XML Files** (`goods.xml`, `offers.xml`, etc.): Moved to `MEDIA_ROOT/1c_import/<type>/`.
2.  **Images** (`.jpg`, `.png`): Moved to `MEDIA_ROOT/1c_import/goods/import_files/`.
3.  **ZIP Files**: Moved to `MEDIA_ROOT/1c_import/` and unpacked during `mode=import` (or `mode=complete`), contents routed as above.

## 4. File System Structure

### 4.1 Temporary Staging (`1c_temp`)
Used for assembling chunks. Contents are ephemeral.

```
/media/1c_temp/
└── <session_id>/
    ├── import.zip  (Incomplete or fully uploaded archive)
    └── goods.xml   (Being assembled)
```

### 4.2 Import Queue (`1c_import`)
Contains fully assembled/unpacked files ready for the Processing Layer.

```
/media/1c_import/
├── goods/
│   ├── goods.xml
│   └── import_files/
│        ├── image1.jpg
│        └── image2.png
└── offers/
    └── offers0_1.xml
```

## 5. Security Measures

1.  **Nginx Protection:**
    - Direct access to `/media/1c_temp/` and `/media/1c_import/` is blocked at the Nginx level to prevent information disclosure.
2.  **Path Traversal Protection:**
    - Filenames in `mode=file` are sanitized (only basename usage).
    - ZIP extraction prevents writing outside the import directory.
3.  **Session Isolation:**
    - Temporary storage uses per-session directories (`1c_temp/<session_id>/`).
    - The import queue is shared (`1c_import/`) and is filled during `mode=import`/`mode=complete`.
