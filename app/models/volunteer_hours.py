# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

class VolunteerHour:
    def __init__(self, id, user_id, date, hours, notes, created_at):
        self.id = id
        self.user_id = user_id
        self.date = date
        self.hours = hours
        self.notes = notes
        self.created_at = created_at

    @staticmethod
    def from_row(row):
        return VolunteerHour(
            id=row[0],
            user_id=row[1],
            date=row[2],
            hours=row[3],
            notes=row[4],
            created_at=row[5]
        )
