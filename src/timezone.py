import datetime
import time
from pytz.gae import pytz


class Mountain_tzinfo(datetime.tzinfo):
    """Implementation of the Pacific timezone."""
    def utcoffset(self, dt):
        return datetime.timedelta(hours=-7) + self.dst(dt)

    def _FirstSunday(self, dt):
        """First Sunday on or after dt."""
        return dt + datetime.timedelta(days=(6-dt.weekday()))

    def dst(self, dt):
        # 2 am on the second Sunday in March
        dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)
    def tzname(self, dt):
        if self.dst(dt) == datetime.timedelta(hours=0):
            return "MST"
        else:
            return "MDT"

def get_mountain_time():
	mountain_time = datetime.datetime.fromtimestamp(
				time.mktime(datetime.datetime.utcnow().timetuple()), Mountain_tzinfo())
	return mountain_time.replace(tzinfo=None)


def back_to_tz(date_time):
	denver_tz = pytz.timezone('America/Denver')
	return denver_tz.localize(date_time, is_dst=None)


def get_today_start():
	today = get_mountain_time().date()
	return datetime.datetime.fromordinal(today.toordinal())


def get_tomorrow_start():
	today = get_mountain_time().date()
	tomorrow = today + datetime.timedelta(1)
	return datetime.datetime.fromordinal(tomorrow.toordinal())
