-- Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
-- 
-- This software is released under the MIT License.
-- https://opensource.org/licenses/MIT

CREATE TABLE IF NOT EXISTS registration_completions (
    id  INTEGER PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    humanid         VARCHAR(255) NOT NULL, -- Human ID of the person who completed the registration
    status VARCHAR(50)           NOT NULL
)