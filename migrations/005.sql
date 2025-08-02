-- Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
-- 
-- This software is released under the MIT License.
-- https://opensource.org/licenses/MIT

CREATE TABLE IF NOT EXISTS volunteer_hours (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES volunteer_users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    hours DECIMAL(4,2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
