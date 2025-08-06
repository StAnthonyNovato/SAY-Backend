# Volunteer Hours API Documentation

This document describes the REST API endpoints for the Volunteer Hours system.

---

## Base URL

    /api/volunteer_hours

---

## Endpoints

### 1. Log Volunteer Hours

**POST** `/api/volunteer_hours/`

- **Description:** Log volunteer hours for a user.
- **Request Body (JSON):**
    - `user_id` (int, required): The user's ID.
    - `date` (string, required): Date in `YYYY-MM-DD` format.
    - `hours` (float, required): Number of hours volunteered.
    - `notes` (string, optional): Any notes about the volunteering.
- **Response:**
    - `201 Created` with the created log entry as JSON.
    - `400 Bad Request` if required fields are missing or invalid.

**Example Request:**
```json
{
  "user_id": 1,
  "date": "2025-08-01",
  "hours": 2.5,
  "notes": "Helped with setup!"
}
```

**Example Response:**
```json
{
  "id": 10,
  "user_id": 1,
  "date": "2025-08-01",
  "hours": 2.5,
  "notes": "Helped with setup!",
  "created_at": "2025-08-01 12:34:56"
}
```

---

### 2. Get All Users

**GET** `/api/volunteer_hours/users`

- **Description:** Retrieve all volunteer users and their IDs.
- **Response:**
    - `200 OK` with a JSON array of users.

**Example Response:**
```json
[
  {"id": 1, "name": "Alice", "email": "alice@example.com"},
  {"id": 2, "name": "Bob", "email": "bob@example.com"}
]
```

---

### 3. Create a New User

**POST** `/api/volunteer_hours/users`

- **Description:** Create a new volunteer user account.
- **Request Body (JSON):**
    - `name` (string, required): User's name.
    - `email` (string, required): User's email (must be unique).
    - `phone` (string, optional): User's phone number.
- **Response:**
    - `201 Created` with the new user as JSON.
    - `400 Bad Request` if required fields are missing.
    - `500 Internal Server Error` if email is not unique.

**Example Request:**
```json
{
  "name": "Charlie",
  "email": "charlie@example.com",
  "phone": "555-1234"
}
```

**Example Response:**
```json
{
  "id": 3,
  "name": "Charlie",
  "email": "charlie@example.com",
  "phone": "555-1234"
}
```

---

### 4. Get All Volunteer Data

**GET** `/api/volunteer_hours/all`

- **Description:** Retrieve all non-deleted volunteer hour logs, including user info.
- **Response:**
    - `200 OK` with a JSON array of all logs.

**Example Response:**
```json
[
  {
    "id": 10,
    "user_id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "date": "2025-08-01",
    "hours": 2.5,
    "notes": "Helped with setup!",
    "created_at": "2025-08-01 12:34:56"
  }
]
```

---

### 5. HTML View of All Data

**GET** `/api/volunteer_hours/view`

- **Description:** View all non-deleted volunteer data in a simple HTML table for quick review.
- **Response:**
    - `200 OK` with an HTML page.

---

### 6. Get Volunteer Summary for a Single User

**GET** `/api/volunteer_hours/view/<id>`

- **Description:** Retrieve all information for a single user, including total hours, name, email, and a list of their non-deleted volunteer history.
- **Response:**
    - `200 OK` with a JSON object containing user info, total hours, and a `history` array of all their volunteer logs.
    - `404 Not Found` if the user does not exist.

**Example Response:**
```json
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com",
  "total_hours": 12.5,
  "history": [
    {
      "id": 10,
      "date": "2025-08-01",
      "hours": 2.5,
      "notes": "Helped with setup!",
      "created_at": "2025-08-01 12:34:56"
    },
    {
      "id": 7,
      "date": "2025-07-15",
      "hours": 3.0,
      "notes": "Food pantry",
      "created_at": "2025-07-15 09:12:34"
    }
  ]
}
```

---

### 7. Delete a Volunteer Hours Entry

**POST** `/api/volunteer_hours/delete/<log_id>`

- **Description:** Soft delete a volunteer hours entry by ID.
- **URL Parameters:**
    - `log_id` (int, required): The ID of the volunteer hours entry to delete.
- **Response:**
    - `200 OK` with a success message if the entry was deleted.
    - `404 Not Found` if the entry doesn't exist or is already deleted.
    - `500 Internal Server Error` if there was a database error.

**Example Response (Success):**
```json
{
  "message": "Volunteer hours entry with ID 10 deleted successfully"
}
```

**Example Response (Not Found):**
```json
{
  "error": "Volunteer hours entry with ID 10 not found"
}
```

---

## Error Responses

- `400 Bad Request`: Missing or invalid fields in the request.
- `404 Not Found`: The requested resource was not found.
- `500 Internal Server Error`: Database or server error.

---

## Notes
- All endpoints are CORS-enabled for use with static web frontends.
- All dates must be in `YYYY-MM-DD` format.
- All responses are `application/json` except for the `/view` endpoint, which returns HTML.
- Soft-deleted entries (where `deleted = TRUE`) are excluded from all data retrieval endpoints.
