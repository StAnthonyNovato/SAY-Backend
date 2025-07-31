-- Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
-- 
-- This software is released under the MIT License.
-- https://opensource.org/licenses/MIT

CREATE TABLE IF NOT EXISTS registrations (
    id           INTEGER PRIMARY KEY AUTO_INCREMENT,
    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    humanid      VARCHAR(255) NOT NULL,
    -- Parent

    -- Regarding phone numbers, I'm not sure of the best way to store these.
    -- I am thinking of one long string, including area code.
    -- So, +1 (800) 123-456 would become 1800123456.
    -- As long as we can ensure this format, including the + number,
    -- we can reconstruct the number in code, or use it at center in a
    -- tel:... URI.
    parent_fname           VARCHAR(255) NOT NULL, -- Parent First Name
    parent_lname           VARCHAR(255) NOT NULL, -- Parent Last Name
    parent_phone           VARCHAR(255) NOT NULL, 
    parent_email           VARCHAR(255) NOT NULL,

    child_fname            VARCHAR(255) NOT NULL,
    child_lname            VARCHAR(255) NOT NULL,
    child_phone            VARCHAR(255)     NULL,
    child_email            VARCHAR(255)     NULL,

    child_baptism          TINYINT(1)   NOT NULL DEFAULT 0, -- 0 = No, 1 = Yes
    child_baptism_date     DATE             NULL,           -- Date of baptism, if applicable
    child_baptism_place    VARCHAR(255)     NULL,           -- Place of baptism, if applicable

    child_first_comm       TINYINT(1)   NOT NULL DEFAULT 0, -- 0 = No, 1 = Yes
    child_first_comm_date  DATE             NULL,           -- Date of first communion, if applicable
    child_first_comm_place VARCHAR(255)     NULL            -- Place of first communion, if applicable
);