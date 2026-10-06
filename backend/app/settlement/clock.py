from datetime import datetime, timezone, timedelta

def now():
    """Business DATETIME columns use Beijing wall time, independent of container TZ."""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
