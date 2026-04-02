import asyncio
from datetime import datetime, timedelta


class ReminderAgent:
    def __init__(self, on_reminder=None):
        self.reminders = []  # List of {id, message, fire_at, task}
        self.on_reminder = on_reminder
        self._counter = 0

    def set_callback(self, on_reminder):
        self.on_reminder = on_reminder

    async def add_reminder(self, message, minutes=0, hours=0, seconds=0):
        """Schedule a reminder after the given delay."""
        total_seconds = seconds + (minutes * 60) + (hours * 3600)
        if total_seconds <= 0:
            return {"error": "Delay must be greater than 0"}

        self._counter += 1
        reminder_id = self._counter
        fire_at = datetime.now() + timedelta(seconds=total_seconds)

        task = asyncio.create_task(self._fire_after(reminder_id, message, total_seconds))

        reminder = {
            "id": reminder_id,
            "message": message,
            "fire_at": fire_at.isoformat(),
            "delay_seconds": total_seconds,
            "task": task,
        }
        self.reminders.append(reminder)

        delay_str = self._format_delay(total_seconds)
        print(f"[REMINDER] Scheduled #{reminder_id}: '{message}' in {delay_str} (at {fire_at.strftime('%H:%M:%S')})")
        return {
            "id": reminder_id,
            "message": message,
            "fire_at": fire_at.isoformat(),
            "delay": delay_str,
        }

    async def _fire_after(self, reminder_id, message, delay):
        """Wait and then fire the reminder."""
        await asyncio.sleep(delay)
        print(f"[REMINDER] Firing #{reminder_id}: '{message}'")
        if self.on_reminder:
            result = self.on_reminder(reminder_id, message)
            # Support async callbacks
            if asyncio.iscoroutine(result):
                await result
        # Remove from active list
        self.reminders = [r for r in self.reminders if r["id"] != reminder_id]

    def cancel_reminder(self, reminder_id):
        """Cancel a pending reminder."""
        for r in self.reminders:
            if r["id"] == reminder_id:
                r["task"].cancel()
                self.reminders.remove(r)
                print(f"[REMINDER] Cancelled #{reminder_id}")
                return True
        return False

    def list_reminders(self):
        """List all pending reminders."""
        return [
            {
                "id": r["id"],
                "message": r["message"],
                "fire_at": r["fire_at"],
            }
            for r in self.reminders
        ]

    @staticmethod
    def _format_delay(seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}m{f' {s}s' if s else ''}"
        else:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            return f"{h}h{f' {m}m' if m else ''}"
